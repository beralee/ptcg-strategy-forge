from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class AuthoringTests(unittest.TestCase):
    def test_editor_schema_and_named_document_use_same_compiler(self):
        from ptcg_strategy_forge.authoring import authoring_metadata, compile_named_rules
        import jsonschema
        rule = {"rule_id": "test.evolve", "stage": "deploy", "option_type": "CARD", "option_uid": "CSV10C_146"}
        jsonschema.validate(rule, authoring_metadata()["macro_rule_schema"])
        source = {"document_type": "forge_named_rules_v1", "schema_version": 1, "adapter_id": "test.adapter", "rules": [rule]}
        result = compile_named_rules(source, allowed_uids={"CSV10C_146"}, deck_sha256="0"*64)
        self.assertEqual("macro_proposal", result["rules"][0]["operator"])
        with self.assertRaises(ValueError):
            compile_named_rules({**source, "execute": "forbidden"}, allowed_uids={"CSV10C_146"}, deck_sha256="0"*64)

    def test_named_rule_compiles_to_existing_data_only_ir(self):
        from ptcg_strategy_forge.authoring import macro_rule, compile_rules
        rule = macro_rule("test.evolve", stage="deploy", option_type="CARD", option_uid="CSV10C_146", hand_uid="CSV10C_147")
        result = compile_rules("test.adapter", [rule], allowed_uids={"CSV10C_146", "CSV10C_147"}, deck_sha256="0"*64)
        self.assertEqual(3, result["rules"][0]["predicate"]["option_type_raw"])
        with self.assertRaisesRegex(ValueError, "authoring_enum_unknown"):
            macro_rule("test.unknown", stage="deploy", option_type="UNSUPPORTED")
        with self.assertRaises(ValueError):
            compile_rules("test.adapter", [rule], allowed_uids={"CSV10C_146"}, deck_sha256="0"*64)

    def test_card_name_discovery_preserves_printing_identity(self):
        from ptcg_strategy_forge.authoring import search_cards
        result = search_cards("玛俐的长毛巨魔")
        self.assertIn("CSV10C_148", {row["card_uid"] for row in result["cards"]})
        self.assertFalse(result["official_card_id_equivalence"])
