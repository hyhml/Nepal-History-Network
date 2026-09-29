"""Regression checks for Rayamajhi's combined visual trajectory."""

import json
import unittest
from pathlib import Path

from build_chart import (
    build_figure,
    build_focus_post_script,
    load_data,
    resolve_lane_header_entries,
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
        dataset_notes = [
            entry["note"] for entry in catalog if entry["kind"] == "datasets"
        ]
        self.assertEqual(len(dataset_titles), 2)
        self.assertTrue(all("二十六位人物" in title for title in dataset_titles))
        self.assertTrue(
            all(f"{organization_count}个真实组织" in note for note in dataset_notes)
        )

        example_readme = (DATA_DIR / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"保存{organization_count}个真实组织", example_readme)
        self.assertIn(f"另有{branch_lane_count}条支线", example_readme)

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
                "relation_national_congress_merger",
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
                "relation_liberation_coordination",
                "relation_coordination_ml",
                "relation_ml_uml",
                "relation_fourth_masal",
                "relation_fourth_mashal_1990",
                "relation_masal_mashal",
                "relation_mashal_unity_centre",
                "relation_unity_people_front",
                "relation_front_maoist",
            }
            <= relation_ids
        )

    def test_1962_to_1968_shared_leadership_stays_in_unified_ncp(self):
        events = self.frames["events"].set_index("event_id")
        self.assertEqual(
            events.loc["event_shrestha_1962_congress", "org_id"], "ncp_unified"
        )
        self.assertEqual(events.loc["event_amatya_gs", "org_id"], "ncp_unified")

        tenures = self.frames["tenures"].set_index("tenure_id")
        self.assertEqual(
            tenures.loc["shrestha_amatya_shared_leadership", "org_id"],
            "ncp_unified",
        )
        self.assertEqual(
            tenures.loc["amatya_unified_leadership", "org_id"], "ncp_unified"
        )
        self.assertEqual(
            str(tenures.loc["amatya_branch_leadership", "start_date"].date()),
            "1968-01-01",
        )

        relations = self.frames["organization_relations"].set_index("relation_id")
        self.assertNotIn("relation_amatya_1962", relations.index)
        self.assertEqual(
            relations.loc["relation_amatya_1968", "source_org_id"], "ncp_unified"
        )
        self.assertEqual(
            relations.loc["relation_amatya_1968", "target_org_id"], "ncp_amatya"
        )
        self.assertEqual(
            relations.loc["relation_shrestha_1968", "source_org_id"], "ncp_unified"
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
                "relation_kawa_kumar_2006",
                "relation_shris_united_2006",
                "relation_unity_masal_unified",
                "relation_maoist_unified",
                "relation_unified_maoist_split_2012",
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

    def test_lineages_share_display_lanes_without_merging_data(self):
        organizations = self.frames["organizations"].set_index("org_id")
        expected_groups = {
            "lane_raimajhi": {
                "raimajhi_controlled_central",
                "ncp_raimajhi",
                "raimajhi_new_party_1983",
                "nepal_people_party_social_democratic",
            },
            "lane_ncp_unified": {
                "ncp_unified",
                "ncp_central_nucleus",
                "ncp_fourth_congress",
            },
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
            "lane_bhandari": {
                "liberation_front_group",
                "all_nepal_communist_revolutionary_coordination_committee_ml",
                "ncp_ml",
            },
            "lane_narayan_kaji": {
                "ncp_unity_centre",
                "ncp_unity_centre_masal",
            },
        }
        self.assertEqual(len(self.frames["organization_lanes"]), 26)
        self.assertEqual(len(self.figure.layout.xaxis.tickvals), 18)
        lane_ids = set(self.frames["organization_lanes"]["lane_id"])
        self.assertFalse({"lane_central_nucleus", "lane_fourth_congress"} & lane_ids)
        for lane_id, org_ids in expected_groups.items():
            self.assertEqual(
                set(organizations.loc[list(org_ids), "lane_id"]), {lane_id}
            )
            self.assertEqual(
                len({organizations.loc[org_id, "name_zh"] for org_id in org_ids}),
                len(org_ids),
            )

    def test_composite_lane_headers_are_vertical_chronologies(self):
        headers = self.frames["organization_lane_headers"].copy()
        self.assertEqual(len(headers), 28)
        self.assertEqual(headers["lane_id"].nunique(), 10)
        self.assertNotIn("label", headers.columns)
        self.assertEqual(
            set(headers["reference_type"]), {"stage", "organization"}
        )
        primary_counts = (
            headers.assign(_primary=headers["is_primary"].eq("yes"))
            .groupby("lane_id")["_primary"]
            .sum()
        )
        self.assertTrue(primary_counts.eq(1).all())

        lane_ids = list(self.figure.layout.meta["organization_lane_axis_ids"])
        tick_texts = dict(zip(lane_ids, self.figure.layout.xaxis.ticktext))
        self.assertEqual(self.figure.layout.xaxis.tickangle, 0)
        self.assertGreaterEqual(self.figure.layout.margin.t, 280)

        resolved = resolve_lane_header_entries(
            headers,
            self.frames["organization_stages"],
            self.frames["organizations"],
        )
        for lane_id, rows in resolved.groupby("lane_id"):
            rows = rows.sort_values("header_order")
            tick = tick_texts[lane_id]
            labels = list(rows["label"])
            self.assertEqual(tick.count("↓"), len(labels) - 1)
            positions = [tick.index(label) for label in labels]
            self.assertEqual(positions, sorted(positions))
            self.assertTrue(rows["start_date"].is_monotonic_increasing)
            for row in rows.itertuples(index=False):
                start_year = row.start_date.year
                end_year = row.end_date.year
                years = str(start_year) if start_year == end_year else f"{start_year}—{end_year}"
                self.assertIn(f"（{years}）", tick)
            primary = rows.loc[rows["is_primary"] == "yes", "label"].item()
            self.assertIn(f"<b>{primary}</b>", tick)

        self.assertNotIn("↓", tick_texts["lane_burma"])
        congress_tick = tick_texts["lane_nepali_congress"]
        self.assertIn("全印尼泊尔国民大会党", congress_tick)
        self.assertIn("尼泊尔国民大会党", congress_tick)
        self.assertIn("<b>大会党</b>", congress_tick)
        self.assertIn("（1950—2012）", congress_tick)
        self.assertNotIn("党禁时期", congress_tick)

    def test_composite_header_references_cannot_drift_from_stages(self):
        frames = {name: frame.copy() for name, frame in self.frames.items()}
        headers = frames["organization_lane_headers"]
        target = headers["reference_id"] == "stage_ncp_raimajhi"
        headers.loc[target, "reference_id"] = "stage_nepal_democratic_congress"
        with self.assertRaisesRegex(ValueError, "lane_id 不一致"):
            validate_references(frames)

    def test_raimajhi_lineage_uses_distinct_real_organization_ids(self):
        stages = self.frames["organization_stages"].set_index("stage_id")
        expected = {
            "stage_contested": "raimajhi_controlled_central",
            "stage_ncp_raimajhi": "ncp_raimajhi",
            "stage_new_party": "raimajhi_new_party_1983",
            "stage_people_party": "nepal_people_party_social_democratic",
        }
        self.assertEqual(
            {stage_id: stages.loc[stage_id, "org_id"] for stage_id in expected},
            expected,
        )
        self.assertEqual(len(set(expected.values())), 4)
        self.assertIn("书中未载党名", stages.loc["stage_new_party", "label"])

        events = self.frames["events"].set_index("event_id")
        self.assertEqual(
            events.loc["event_1991_people_party", "org_id"],
            "nepal_people_party_social_democratic",
        )
        tenures = self.frames["tenures"].set_index("tenure_id")
        self.assertEqual(
            tenures.loc["raimajhi_post_1983_party", "org_id"],
            "raimajhi_new_party_1983",
        )

    def test_short_lived_single_person_orgs_are_branch_nodes(self):
        lanes = self.frames["organization_lanes"].set_index("lane_id")
        organizations = self.frames["organizations"].set_index("org_id")
        expected = {
            "ncp_masal_sharma": "lane_masal_sharma",
            "united_peoples_front_vaidya": "lane_people_front_vaidya",
            "ncp_marxist_leninist_1998": "lane_uml_pradhan_1998_branch",
            "national_democratic_party": "lane_national_democratic_party_branch",
            "ncp_2006_kawa_kumar": "lane_ncp_2006_branch",
            "ncp_united_2006": "lane_ncp_united_2006_branch",
            "ncp_maoist_2012": "lane_ncp_maoist_2012_branch",
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
        self.assertEqual(len(stages), 35)
        labels = set(stages["label"])
        self.assertTrue(
            {
                "尼共〔统一时期〕",
                "尼共中央核心小组",
                "尼共（四大）",
                "尼泊尔工农党",
                "尼共（民主派）",
                "统一尼共（毛）",
                "尼共（马）",
                "尼共（马列）",
                "尼共（团结中心—Masal）",
                "尼共（团结中心）（纳拉扬·卡吉派）",
                "全尼泊尔共产主义革命协调委员会（马列主义者）",
                "尼泊尔人民统一战线〔初建政治阵线〕",
                "尼泊尔人民统一战线〔巴特拉伊重建〕",
                "尼泊尔共产党（2006）",
                "尼共（统一）〔什里斯派转入〕",
                "尼共—毛〔2012年分出〕",
            }
            <= labels
        )
        relation_ids = set(self.frames["organization_relations"]["relation_id"])
        self.assertIn("relation_nucleus_fourth_congress", relation_ids)
        meta = self.figure.layout.meta
        self.assertEqual(len(meta["focus_stage_annotations"]), len(stages))
        self.assertTrue(
            all("related_person_ids" in item for item in meta["focus_stage_annotations"])
        )

        script = build_focus_post_script(self.frames["people"])
        self.assertIn("item.related_person_ids", script)
        self.assertIn("focus_stage_annotations", script)

    def test_seven_accepted_lineage_clarifications_stay_explicit(self):
        organizations = self.frames["organizations"].set_index("org_id")
        relations = self.frames["organization_relations"].set_index("relation_id")
        stages = self.frames["organization_stages"].set_index("stage_id")
        tenures = self.frames["tenures"].set_index("tenure_id")
        events = self.frames["events"].set_index("event_id")

        self.assertEqual(relations.loc["relation_united_uml", "relation_type"], "partial_merge")
        self.assertEqual(str(stages.loc["stage_manandhar_united", "end_date"].date()), "2005-01-01")

        self.assertEqual(relations.loc["relation_fourth_mashal_1990", "relation_type"], "partial_merge")
        self.assertIn("大部分", relations.loc["relation_fourth_mashal_1990", "description"])
        self.assertEqual(relations.loc["relation_fourth_unity_centre", "relation_type"], "partial_merge")
        self.assertIn("一小部分", relations.loc["relation_fourth_unity_centre", "description"])

        self.assertEqual(
            organizations.loc["ncp_maoist_2012", "lane_id"],
            "lane_ncp_maoist_2012_branch",
        )
        self.assertEqual(
            events.loc["event_prachanda_split_2012", "org_id"],
            "unified_ncp_maoist",
        )
        self.assertNotIn(
            "mohan_vaidya",
            relations.loc["relation_unified_maoist_split_2012", "related_person_ids"],
        )

        self.assertEqual(
            events.loc["event_bhandari_coordination", "org_id"],
            "all_nepal_communist_revolutionary_coordination_committee_ml",
        )
        self.assertEqual(
            tenures.loc["bhandari_coordination", "org_id"],
            "all_nepal_communist_revolutionary_coordination_committee_ml",
        )
        self.assertEqual(str(tenures.loc["bhandari_ml", "start_date"].date()), "1986-01-01")
        self.assertEqual(relations.loc["relation_coordination_ml", "date_precision"], "uncertain")

        self.assertEqual(
            organizations.loc["ncp_2006_kawa_kumar", "lane_id"],
            "lane_ncp_2006_branch",
        )
        self.assertEqual(
            organizations.loc["ncp_united_2006", "lane_id"],
            "lane_ncp_united_2006_branch",
        )

        self.assertEqual(tenures.loc["baburam_people_front_initial", "track"], "front")
        self.assertEqual(tenures.loc["baburam_people_front_rebuilt", "track"], "front")
        self.assertEqual(relations.loc["relation_front_maoist", "relation_type"], "cofounded")
        self.assertEqual(
            stages.loc["stage_people_front_initial", "end_date"],
            stages.loc["stage_people_front_rebuilt", "start_date"],
        )
        front_hovers = [
            trace.text[0]
            for trace in self.figure.data
            if isinstance(trace.meta, dict)
            and trace.meta.get("person_id") == "baburam_bhattarai"
            and trace.mode == "lines"
            and len(trace.x) == 2
            and "人民统一战线" in str(trace.text[0])
        ]
        self.assertTrue(front_hovers)
        self.assertTrue(all("政治阵线任职" in hover for hover in front_hovers))

        self.assertEqual(
            relations.loc["relation_national_congress_merger", "target_org_id"],
            "nepali_congress",
        )
        self.assertEqual(
            relations.loc["relation_democratic_congress_merger", "target_org_id"],
            "nepali_congress",
        )

        partial_trace = next(
            trace
            for trace in self.figure.data
            if "<b>部分并入</b>" in str(trace.hovertemplate)
        )
        cofounded_trace = next(
            trace
            for trace in self.figure.data
            if "<b>共同组建</b>" in str(trace.hovertemplate)
        )
        self.assertEqual(partial_trace.line.dash, "dot")
        self.assertEqual(cofounded_trace.line.dash, "dash")

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
        self.assertIn("function updateStickyLaneHeader()", script)
        self.assertIn("plotly_relayout", script)
        self.assertIn("<h4>使用说明</h4>", script)
        self.assertIn("100%／60%／20%只是透明度", script)
        self.assertIn("点击它不会选中后面的整列", script)
        self.assertIn("<b>列头 ↓：</b>", script)
        self.assertIn("已选组织谱系：", script)
        self.assertNotIn("组织成员为 60%", script)


if __name__ == "__main__":
    unittest.main()
