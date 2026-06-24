import base64
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "ppt_goal.py"
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class PptGoalCliTests(unittest.TestCase):
    def run_cli(self, *args, input_text=None, check=True):
        result = subprocess.run(
            ["python3", str(CLI), *args],
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(f"command failed: {result.args}\nstdout={result.stdout}\nstderr={result.stderr}")
        return result

    def init_run(self, tmp, mode="spark", style="style_description", extra=None):
        run = Path(tmp) / "demo-001"
        args = [
            "init",
            "--run",
            str(run),
            "--mode",
            mode,
            "--title",
            "AI History",
            "--aspect",
            "16:9",
            "--language",
            "zh",
            "--style-source",
            style,
        ]
        if style == "style_description":
            args += ["--style-description", "科技现代，深色背景，高对比信息层级"]
        if extra:
            args += extra
        self.run_cli(*args)
        return run

    def state(self, run):
        return json.loads((run / "STATE.json").read_text(encoding="utf-8"))

    def write_artifact(self, run, stage, text):
        self.run_cli("write-artifact", "--run", str(run), "--stage", stage, "--stdin", input_text=text)

    def test_colon_triggers_are_aliases_not_skill_names(self):
        expected = {
            "spark": "/codex-ai-ppt:spark",
            "outline": "/codex-ai-ppt:outline",
            "brief": "/codex-ai-ppt:brief",
        }
        skill_dirs = sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir())
        self.assertEqual(skill_dirs, ["brief", "outline", "spark"])
        self.assertTrue((ROOT / "references" / "codex-ai-ppt-workflow.md").exists())
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIsInstance(manifest["interface"]["defaultPrompt"], list)
        default_prompt_text = "\n".join(manifest["interface"]["defaultPrompt"])

        for skill_name, alias in expected.items():
            skill_md = ROOT / "skills" / skill_name / "SKILL.md"
            text = skill_md.read_text(encoding="utf-8")
            frontmatter = text.split("---", 2)[1]
            self.assertIn(f"name: {skill_name}", frontmatter)
            self.assertNotIn(f"name: {alias}", frontmatter)
            self.assertIn(alias, text)
            self.assertIn(alias, default_prompt_text)

    def test_init_modes_create_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ["spark", "outline", "brief"]:
                run = self.init_run(Path(tmp) / mode, mode=mode)
                state = self.state(run)
                self.assertEqual(state["mode"], mode)
                self.assertEqual(state["aspect"], "16:9")
                self.assertTrue((run / "CONTRACT.md").exists())
                self.assertTrue((run / "prompts").is_dir())

    def test_validate_style_source_finds_missing_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "missing-001"
            self.run_cli(
                "init",
                "--run",
                str(run),
                "--mode",
                "spark",
                "--title",
                "No Style",
                "--style-source",
                "style_description",
            )
            result = self.run_cli("validate-style-source", "--run", str(run), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("style_source.style_description is required", result.stderr)

    def test_template_image_is_copied_and_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "template.png"
            template.write_bytes(PNG_BYTES)
            run = self.init_run(tmp, style="template_image", extra=["--template-image", str(template)])
            self.run_cli("validate-style-source", "--run", str(run))
            state = self.state(run)
            self.assertEqual(state["style_source"]["type"], "template_image")
            self.assertTrue((run / state["style_source"]["template_image"]).exists())

    def test_outline_mode_preserves_user_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.init_run(tmp, mode="outline")
            outline = "# 第一部分：背景\n## AI 的起源\n- 图灵测试\n- 符号主义\n## 深度学习爆发\n- 算力增长\n- 数据规模\n"
            self.write_artifact(run, "outline", outline)
            self.assertEqual((run / "OUTLINE.md").read_text(encoding="utf-8"), outline)

    def test_brief_mode_description_and_light_outline(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.init_run(tmp, mode="brief")
            outline = "## page-001 封面\n- AI 历史\n## page-002 关键节点\n- 从图灵到深度学习\n"
            descriptions = "## page-001 封面\nVisible text:\nAI 历史\n\n## page-002 关键节点\nVisible text:\n图灵测试 / 专家系统 / 深度学习\n"
            self.write_artifact(run, "outline", outline)
            self.write_artifact(run, "descriptions", descriptions)
            result = self.run_cli("validate", "--run", str(run), "--stage", "descriptions")
            self.assertIn("descriptions: ok", result.stdout)

    def test_validate_image_plan_requires_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.init_run(tmp)
            self.write_artifact(run, "descriptions", "## page-001 封面\nVisible text:\nAI 历史\n")
            self.write_artifact(run, "image-plan", "## page-001 封面\nPrompt: prompts/page-001.md\n")
            result = self.run_cli("validate", "--run", str(run), "--stage", "image-plan", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing prompt for page-001", result.stderr)

    def test_version_add_activate_export_and_final_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.init_run(tmp)
            descriptions = "## page-001 封面\nVisible text:\nAI 历史\n\n## page-002 时间线\nVisible text:\n1950 到今天\n"
            plan = "## page-001 封面\nPrompt: prompts/page-001.md\n\n## page-002 时间线\nPrompt: prompts/page-002.md\n"
            self.write_artifact(run, "descriptions", descriptions)
            self.write_artifact(run, "image-plan", plan)

            for idx in [1, 2]:
                prompt = run / f"tmp-page-{idx:03d}.md"
                prompt.write_text(f"prompt {idx}", encoding="utf-8")
                image = run / f"tmp-page-{idx:03d}.png"
                image.write_bytes(PNG_BYTES)
                result = self.run_cli(
                    "version-add",
                    "--run",
                    str(run),
                    "--page",
                    f"page-{idx:03d}",
                    "--image",
                    str(image),
                    "--prompt",
                    str(prompt),
                )
                self.assertIn("v001", result.stdout)

            self.run_cli("version-activate", "--run", str(run), "--page", "page-001", "--version", "v001")
            out = run / "exports" / "deck.pptx"
            self.run_cli("export-pptx", "--run", str(run), "--out", str(out))
            self.assertTrue(zipfile.is_zipfile(out))
            with zipfile.ZipFile(out) as z:
                names = set(z.namelist())
            self.assertIn("ppt/slides/slide1.xml", names)
            self.assertIn("ppt/media/image2.png", names)
            events = (run / "events.jsonl").read_text(encoding="utf-8")
            self.assertRegex(events, r"export_pptx_(artifact_tool|fallback)")
            if (Path("/Users/hola/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool").exists()):
                self.assertIn("export_pptx_artifact_tool", events)
                self.assertNotIn("export_pptx_fallback", events)

            final = self.run_cli("final-status", "--run", str(run), "--json")
            payload = json.loads(final.stdout)
            self.assertTrue(payload["ready"])

    def test_smart_merge_outline_preserves_existing_slide_id_and_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.init_run(tmp)
            self.write_artifact(run, "outline", "## page-001 旧标题\n- A\n## page-002 第二页\n- B\n")
            state = self.state(run)
            state["active_versions"]["page-001"] = "v001"
            (run / "STATE.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            self.run_cli("smart-merge-outline", "--run", str(run), "--stdin", input_text="## page-001 新标题\n- A2\n## page-003 新增\n- C\n")
            merged = self.state(run)
            self.assertEqual(merged["pages"][0]["slide_id"], "page-001")
            self.assertIn("page-002", merged["orphaned_pages"])
            self.assertIn("images", merged["stale"])
            self.assertEqual(merged["active_versions"]["page-001"], "v001")


if __name__ == "__main__":
    unittest.main()
