"""Regression checks for Rayamajhi's combined visual trajectory."""

import unittest
from pathlib import Path

from build_chart import (
    build_figure,
    build_focus_post_script,
    load_data,
    validate_references,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "examples" / "raimajhi-life"


class RaimajhiHoverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = load_data(DATA_DIR)
        validate_references(cls.frames)
        cls.figure = build_figure(cls.frames, "test")

    def test_party_and_public_roles_share_one_axis(self):
        for table_name in ("tenures", "events"):
            rows = self.frames[table_name]
            offsets = rows.loc[rows["person_id"] == "raimajhi", "x_offset"]
            self.assertTrue(all(value in ("", "0") for value in offsets))

        person_traces = [
            trace
            for trace in self.figure.data
            if isinstance(trace.meta, dict) and trace.meta.get("person_id") == "raimajhi"
        ]
        self.assertTrue(person_traces)
        self.assertTrue(all(float(x).is_integer() for trace in person_traces for x in trace.x))

    def test_hover_distinguishes_roles_without_losing_excerpts(self):
        person_traces = [
            trace
            for trace in self.figure.data
            if isinstance(trace.meta, dict) and trace.meta.get("person_id") == "raimajhi"
        ]
        event_trace = next(trace for trace in person_traces if trace.mode == "markers+text")
        event_hovers = [item[0] for item in event_trace.customdata]
        self.assertTrue(any("党内事件" in item and "1957年" in item for item in event_hovers))
        self.assertTrue(any("党外任职" in item and "教育大臣" in item for item in event_hovers))
        self.assertTrue(any("生平事件" in item and "2012年" in item for item in event_hovers))

        tenure_hovers = [trace.text[0] for trace in person_traces if trace.mode == "lines+markers"]
        self.assertTrue(any("党内任职" in item for item in tenure_hovers))
        public_hover = next(item for item in tenure_hovers if "过渡政府教育大臣" in item)
        self.assertIn("党外任职", public_hover)
        self.assertNotIn("尼共（腊伊玛吉）", public_hover)

    def test_background_is_dimmed_and_structured(self):
        backgrounds = self.frames["background_events"]
        self.assertGreaterEqual(len(backgrounds), 15)
        self.assertTrue(backgrounds["governing_authority"].str.strip().ne("").all())
        self.assertTrue(backgrounds["india_relations"].str.strip().ne("").all())

        background_traces = [
            trace
            for trace in self.figure.data
            if trace.name in {"政治背景", "政治背景时期"}
        ]
        self.assertTrue(background_traces)
        self.assertTrue(all(trace.opacity == 0.16 for trace in background_traces))
        point_trace = next(trace for trace in background_traces if trace.name == "政治背景")
        hovers = [item[0] for item in point_trace.customdata]
        self.assertTrue(all("当权者：" in item and "对印关系：" in item for item in hovers))

        known_sources = set(self.frames["sources"]["source_id"])
        used_sources = {
            source_id
            for value in backgrounds["source_id"]
            for source_id in value.split(";")
        }
        self.assertFalse(used_sources - known_sources)

    def test_prachanda_is_the_default_focus(self):
        script = build_focus_post_script(self.frames["people"])
        self.assertIn("const defaultSelection = ['prachanda'];", script)
        self.assertIn("function resetToDefault() { resetViewAndControls(defaultSelection); }", script)
        self.assertIn("function showAllPeople()", script)


if __name__ == "__main__":
    unittest.main()
