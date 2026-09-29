"""Regression checks for Rayamajhi's combined visual trajectory."""

import json
import unittest
from pathlib import Path

from build_chart import (
    build_figure,
    build_focus_post_script,
    load_data,
    validate_references,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "examples" / "raimajhi-life"
FIRST_BATCH = {
    "baburam_bhattarai",
    "tulsi_lal_amatya",
    "nirmal_lama",
    "mohan_vaidya",
    "sahana_pradhan",
    "madan_bhandari",
    "bishnu_manandhar",
    "krishna_raj_burma",
}
SECOND_BATCH = {
    "narayan_man_bijukchhe",
    "shambhu_ram_shrestha",
    "dina_nath_sharma",
    "narayan_kaji_shrestha",
    "niranjan_govinda_vaidya",
    "madhav_kumar_nepal",
    "ram_bahadur_thapa",
    "chandra_prasad_gajurel",
}
CONGRESS_BATCH = {
    "bp_koirala",
    "matrika_prasad_koirala",
    "krishna_prasad_bhattarai",
    "girija_prasad_koirala",
    "sher_bahadur_deuba",
}


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
            if isinstance(trace.meta, dict)
            and trace.meta.get("person_id") == "raimajhi"
            and trace.mode == "lines"
            and len(trace.x) == 2
            and not any(x is None for x in trace.x)
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

        tenure_hovers = [
            trace.text[0]
            for trace in person_traces
            if trace.mode == "lines"
            and len(trace.x) == 2
            and not any(x is None for x in trace.x)
        ]
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
        period_traces = [
            trace for trace in background_traces if trace.name == "政治背景时期"
        ]
        self.assertEqual(len(period_traces), 1)

    def test_first_batch_has_people_events_tenures_and_focus_entries(self):
        person_ids = set(self.frames["people"]["person_id"])
        self.assertEqual(len(person_ids), 26)
        self.assertTrue(FIRST_BATCH <= person_ids)

        for table_name in ("events", "tenures"):
            represented = set(self.frames[table_name]["person_id"])
            self.assertTrue(FIRST_BATCH <= represented)

        script = build_focus_post_script(self.frames["people"])
        for person_id in FIRST_BATCH:
            self.assertIn(f'"id": "{person_id}"', script)

    def test_project_summaries_match_current_dataset_counts(self):
        people_count = len(self.frames["people"])
        organization_count = len(self.frames["organizations"])
        lanes = self.frames["organization_lanes"]
        main_lane_count = int((lanes["lane_type"] == "main").sum())
        branch_lane_count = int((lanes["lane_type"] == "branch").sum())

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            f"{people_count}个人物、{organization_count}个真实组织、"
            f"{main_lane_count}条主列和{branch_lane_count}条支线节点",
            readme,
        )

        catalog = json.loads(
            (ROOT / "materials" / "catalog.json").read_text(encoding="utf-8")
        )
        dataset_titles = [
            entry["title"] for entry in catalog if entry["kind"] == "datasets"
        ]
        self.assertEqual(len(dataset_titles), 2)
        self.assertTrue(all("二十六位人物" in title for title in dataset_titles))

        public_html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(public_html.count('"id": "sher_bahadur_deuba"'), 1)
        for person_id in self.frames["people"]["person_id"]:
            self.assertIn(f'"id": "{person_id}"', public_html)

    def test_second_batch_has_people_events_tenures_and_focus_entries(self):
        person_ids = set(self.frames["people"]["person_id"])
        self.assertTrue(SECOND_BATCH <= person_ids)

        for table_name in ("events", "tenures"):
            represented = set(self.frames[table_name]["person_id"])
            self.assertTrue(SECOND_BATCH <= represented)

        script = build_focus_post_script(self.frames["people"])
        for person_id in SECOND_BATCH:
            self.assertIn(f'"id": "{person_id}"', script)

    def test_congress_history_has_leaders_stages_and_government_roles(self):
        person_ids = set(self.frames["people"]["person_id"])
        self.assertTrue(CONGRESS_BATCH <= person_ids)
        for table_name in ("events", "tenures"):
            represented = set(self.frames[table_name]["person_id"])
            self.assertTrue(CONGRESS_BATCH <= represented)

        organizations = self.frames["organizations"].set_index("org_id")
        self.assertEqual(organizations.loc["nepal_national_congress", "lane_id"], "lane_nepali_congress")
        self.assertEqual(organizations.loc["nepali_congress", "lane_id"], "lane_nepali_congress")
        self.assertEqual(
            organizations.loc["national_democratic_party", "lane_id"],
            "lane_national_democratic_party_branch",
        )
        congress_people = set(
            self.figure.layout.meta["organization_lane_people"]["lane_nepali_congress"]
        )
        self.assertTrue(CONGRESS_BATCH <= congress_people)

        relation_ids = set(self.frames["organization_relations"]["relation_id"])
        self.assertTrue(
            {
                "relation_national_democratic_congress",
                "relation_democratic_congress_merger",
                "relation_matrika_national_democratic",
            }
            <= relation_ids
        )
        labels = set(self.frames["organization_stages"]["label"])
        self.assertTrue(
            {
                "全印尼泊尔国民大会党",
                "尼泊尔国民大会党",
                "大会党〔党禁时期〕",
                "大会党〔七党联盟时期〕",
            }
            <= labels
        )

        gp_traces = [
            trace
            for trace in self.figure.data
            if isinstance(trace.meta, dict)
            and trace.meta.get("person_id") == "girija_prasad_koirala"
        ]
        tenure_hovers = [
            trace.text[0]
            for trace in gp_traces
            if trace.mode == "lines" and len(trace.x) == 2
        ]
        self.assertTrue(any("政府任职" in hover for hover in tenure_hovers))

    def test_first_batch_organization_paths_are_present(self):
        relation_ids = set(self.frames["organization_relations"]["relation_id"])
        self.assertTrue(
            {
                "relation_burma_split",
                "relation_manandhar_united",
                "relation_united_uml",
                "relation_pushpa_liberation",
                "relation_liberation_ml",
                "relation_ml_uml",
                "relation_fourth_masal",
                "relation_masal_mashal",
                "relation_mashal_unity_centre",
                "relation_unity_people_front",
                "relation_front_maoist",
            }
            <= relation_ids
        )

    def test_all_fact_source_references_resolve(self):
        known_sources = set(self.frames["sources"]["source_id"])
        for table_name in ("events", "tenures", "organization_relations"):
            used_sources = {
                source_id.strip()
                for value in self.frames[table_name]["source_id"]
                for source_id in value.split(";")
                if source_id.strip()
            }
            self.assertFalse(used_sources - known_sources, table_name)

    def test_second_batch_paths_and_similar_names_stay_distinct(self):
        relation_ids = set(self.frames["organization_relations"]["relation_id"])
        self.assertTrue(
            {
                "relation_pushpa_workers_org",
                "relation_workers_org_party",
                "relation_ncp_central_nucleus",
                "relation_masal_sharma",
                "relation_sharma_maoist",
                "relation_people_front_vaidya",
                "relation_unity_masal_unified",
                "relation_maoist_unified",
            }
            <= relation_ids
        )
        niranjan_orgs = set(
            self.frames["events"].loc[
                self.frames["events"]["person_id"] == "niranjan_govinda_vaidya",
                "org_id",
            ]
        )
        self.assertNotIn("ncp_fourth_congress", niranjan_orgs)
        self.assertNotEqual("niranjan_govinda_vaidya", "mohan_vaidya")

        transition_traces = [
            trace
            for trace in self.figure.data
            if isinstance(trace.meta, dict)
            and trace.meta.get("person_id")
            and trace.mode == "lines"
            and any(value is None for value in trace.x)
        ]
        self.assertLessEqual(len(transition_traces), 2 * len(self.frames["people"]))

    def test_six_lineages_share_display_lanes_without_merging_data(self):
        organizations = self.frames["organizations"].set_index("org_id")
        expected_groups = {
            "lane_rohit": {
                "nepal_workers_peasants_org",
                "nepal_workers_peasants_party",
            },
            "lane_manandhar": {"ncp_manandhar", "ncp_united_1991"},
            "lane_prachanda": {
                "ncp_unity_centre_prachanda",
                "ncp_maoist",
                "unified_ncp_maoist",
            },
            "lane_pradhan": {"ncp_pushpa_lal", "ncp_marxist"},
            "lane_bhandari": {"liberation_front_group", "ncp_ml"},
            "lane_narayan_kaji": {
                "ncp_unity_centre",
                "ncp_unity_centre_masal",
            },
        }
        self.assertEqual(len(self.frames["organization_lanes"]), 25)
        self.assertEqual(len(self.figure.layout.xaxis.tickvals), 20)
        for lane_id, org_ids in expected_groups.items():
            self.assertEqual(
                set(organizations.loc[list(org_ids), "lane_id"]), {lane_id}
            )
            self.assertEqual(
                len({organizations.loc[org_id, "name_zh"] for org_id in org_ids}),
                len(org_ids),
            )

    def test_short_lived_single_person_orgs_are_branch_nodes(self):
        lanes = self.frames["organization_lanes"].set_index("lane_id")
        organizations = self.frames["organizations"].set_index("org_id")
        expected = {
            "ncp_masal_sharma": "lane_masal_sharma",
            "united_peoples_front_vaidya": "lane_people_front_vaidya",
            "ncp_marxist_leninist_1998": "lane_uml_pradhan_1998_branch",
            "national_democratic_party": "lane_national_democratic_party_branch",
        }
        for org_id, lane_id in expected.items():
            self.assertEqual(organizations.loc[org_id, "lane_id"], lane_id)
            self.assertEqual(lanes.loc[lane_id, "lane_type"], "branch")
            self.assertIn(lanes.loc[lane_id, "parent_lane_id"], lanes.index)
            self.assertNotEqual(float(lanes.loc[lane_id, "branch_offset"]), 0.0)
        branch_annotations = self.figure.layout.meta["focus_branch_annotations"]
        self.assertEqual(len(branch_annotations), 4)
        self.assertTrue(all(item["related_person_ids"] for item in branch_annotations))

    def test_lineage_stages_keep_person_specific_focus_metadata(self):
        stages = self.frames["organization_stages"]
        self.assertEqual(len(stages), 26)
        labels = set(stages["label"])
        self.assertTrue(
            {
                "尼泊尔工农党",
                "尼共（民主派）",
                "统一尼共（毛）",
                "尼共（马）",
                "尼共（马列）",
                "尼共（团结中心—Masal）",
                "尼共（团结中心）（纳拉扬·卡吉派）",
            }
            <= labels
        )
        meta = self.figure.layout.meta
        self.assertEqual(len(meta["focus_stage_annotations"]), len(stages))
        self.assertTrue(
            all("related_person_ids" in item for item in meta["focus_stage_annotations"])
        )

        script = build_focus_post_script(self.frames["people"])
        self.assertIn("item.related_person_ids", script)
        self.assertIn("focus_stage_annotations", script)

    def test_prachanda_is_the_default_focus(self):
        script = build_focus_post_script(self.frames["people"])
        self.assertIn("const defaultSelection = ['prachanda'];", script)
        self.assertIn("return 0.2", script)
        self.assertNotIn("0.07", script)
        for trace in self.figure.data:
            if trace.name == "政治背景" or trace.name == "政治背景时期":
                self.assertEqual(trace.opacity, 0.16)
            elif trace.opacity is not None:
                self.assertEqual(trace.opacity, 0.20)
        self.assertIn("function resetToDefault() { resetViewAndControls(defaultSelection); }", script)
        self.assertIn("function showAllPeople()", script)


if __name__ == "__main__":
    unittest.main()
