"""Agentni baholaydi: python manage.py eval_agent

    --list                 holatlar ro'yxatini ko'rsatadi (LLM ishlatilmaydi)
    --validate             ma'lumotlar to'plamini tekshiradi (LLM ishlatilmaydi)
    --tags slots,security  faqat shu teglar
    --ids book_flow_uz     faqat shu holatlar
    --limit 5              birinchi N ta holat
    --sleep 3              turlar orasida kutish (soniya): bepul LLM limitidan oshmaslik uchun

Daqiqalik limit (429) chiqsa, buyruq kutib qayta urinadi; kunlik limit tugasa, to'xtaydi va sababini yozadi.
Diqqat: har bir holat bir necha LLM so'rovi sarflaydi. Bepul limit kichik bo'lsa, avval --limit bilan sinang.
Natija eval_reports/latest.md va eval_reports/<vaqt>.json fayllariga yoziladi.
"""
import json
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ai.evals.cases import CASES, KNOWN_SETUPS
from apps.ai.evals.ratelimit import is_daily_limit, parse_retry_delay
from apps.ai.evals.scoring import render_markdown, summarize, validate_cases
from apps.ai.llm import conf


class Command(BaseCommand):
    help = "AI agentni ma'lumotlar to'plami bo'yicha baholaydi va hisobot yozadi"

    def add_arguments(self, parser):
        parser.add_argument("--list", action="store_true")
        parser.add_argument("--validate", action="store_true")
        parser.add_argument("--tags", default="")
        parser.add_argument("--ids", default="")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--sleep", type=float, default=2.0)
        parser.add_argument("--output-dir", default="eval_reports")

    def handle(self, *args, **opts):
        problems = validate_cases(CASES, KNOWN_SETUPS)
        if problems:
            raise CommandError("Ma'lumotlar to'plamida xatolar:\n- " + "\n- ".join(problems))

        cases = self._select(opts)
        if opts["validate"]:
            self.stdout.write(self.style.SUCCESS(f"To'plam to'g'ri: {len(CASES)} ta holat."))
            return
        if opts["list"]:
            for case in cases:
                self.stdout.write(f"{case['id']:32} {','.join(case['tags']):28} {len(case['turns'])} tur")
            self.stdout.write(f"Jami: {len(cases)} ta holat")
            return
        if not cases:
            raise CommandError("Tanlangan filtr bo'yicha holat topilmadi.")

        self._run(cases, opts)

    def _select(self, opts):
        cases = CASES
        if opts["ids"]:
            wanted = {x.strip() for x in opts["ids"].split(",") if x.strip()}
            cases = [c for c in cases if c["id"] in wanted]
        if opts["tags"]:
            wanted = {x.strip() for x in opts["tags"].split(",") if x.strip()}
            cases = [c for c in cases if wanted & set(c["tags"])]
        if opts["limit"] > 0:
            cases = cases[: opts["limit"]]
        return cases

    def _run(self, cases, opts):
        from apps.ai.evals.runner import EvalEnv, fixed_today
        from apps.ai.views import _get_runner

        env = EvalEnv()
        runner = _get_runner()
        results = []
        note = ""
        self.stdout.write(f"{len(cases)} ta holat, baholash sanasi: {env.today} (Dushanba)\n")
        try:
            with fixed_today(env.today):
                for case in cases:
                    res, stop_note = self._run_case(case, env, runner, opts["sleep"])
                    if res is None:
                        note = stop_note
                        self.stdout.write(self.style.ERROR(f"{case['id']}: to'xtatildi. {stop_note}"))
                        break
                    results.append(res)
                    self._print_case(res)
        finally:
            env.cleanup()

        if not results:
            raise CommandError("Birorta holat ishga tushmadi. " + note)

        summary = summarize(results)
        meta = {
            "sana": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "model": conf("LLM_MODEL", "?"),
            "engine": conf("AI_ENGINE", "graph"),
            "eslatma": note,
        }
        self._write_reports(opts["output_dir"], summary, results, meta)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Natija: {summary['passed']}/{summary['total']} ({summary['pass_rate']:.0%})"))
        for cat, row in summary["by_category"].items():
            self.stdout.write(f"  {cat:15} {row['passed']}/{row['total']} ({row['rate']:.0%})")

    MAX_RATE_WAITS = 3

    @staticmethod
    def _error_text(exc) -> str:
        """Xato matni + provayder javobining tanasi (str(exc) ba'zan faqat 'Error code: 429' bo'ladi)."""
        text = str(exc)
        response = getattr(exc, "response", None)
        try:
            body = response.text if response is not None else ""
        except Exception:
            body = ""
        return f"{text} {body}".strip() if body and body not in text else text

    def _run_case(self, case, env, runner, sleep):
        """Holatni ishga tushiradi. 429 da: kunlik limit bo'lsa to'xtaydi, aks holda kutib qayta urinadi.
        Qaytaradi: (natija, None) yoki (None, to'xtash sababi)."""
        from openai import RateLimitError

        from apps.ai.evals.runner import run_case

        waits = 0
        while True:
            try:
                return run_case(case, env, runner, sleep=sleep), None
            except RateLimitError as exc:
                text = self._error_text(exc)
                self.stdout.write(self.style.WARNING(f"{case['id']}: 429. Provayder xabari: {text[:600]}"))
                if is_daily_limit(text):
                    return None, ("Kunlik limit tugadi (bepul reja). Ertaga davom eting, "
                                  "boshqa model (LLM_MODEL) yoki boshqa provayder tanlang.")
                waits += 1
                if waits > self.MAX_RATE_WAITS:
                    return None, ("Daqiqalik limit qayta-qayta tugadi. --sleep ni oshiring (masalan 12) "
                                  "yoki limiti yuqoriroq model tanlang.")
                headers = getattr(getattr(exc, "response", None), "headers", None) or {}
                delay = parse_retry_delay(text, headers.get("retry-after"))
                self.stdout.write(f"   {delay:.0f} soniya kutamiz, so'ng qayta urinamiz ({waits}/{self.MAX_RATE_WAITS})...")
                time.sleep(delay)

    def _print_case(self, res):
        if res.passed:
            self.stdout.write(self.style.SUCCESS(f"✓ {res.case_id}  ({res.latency_s:.1f} s)"))
            return
        self.stdout.write(self.style.ERROR(f"✗ {res.case_id}"))
        if res.error:
            self.stdout.write(f"    XATO: {res.error}")
        for check in res.failures():
            self.stdout.write(f"    - {check.name}: {check.detail}")

    def _write_reports(self, output_dir, summary, results, meta):
        out = Path(settings.BASE_DIR) / output_dir
        out.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (out / "latest.md").write_text(render_markdown(summary, results, meta), encoding="utf-8")
        payload = {"meta": meta, "summary": summary, "cases": [r.to_dict() for r in results]}
        (out / f"{stamp}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(f"\nHisobot: {out / 'latest.md'}")
