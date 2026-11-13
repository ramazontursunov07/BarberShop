"""AI sarfi va tezligi hisoboti (kurs ishi hisoboti uchun raqamlar):

    python manage.py llm_report                     # oxirgi 7 kun, haqiqiy so'rovlar
    python manage.py llm_report --days 30 --include-eval
    python manage.py llm_report --json              # mashina o'qiydigan ko'rinish
    python manage.py llm_report --csv eval_reports/traces.csv   # har bir so'rov uchun bir qator
"""
import csv
import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.ai.models import ChatTrace
from apps.ai.usage_stats import usage_stats


def _ms(value) -> str:
    return "-" if value is None else f"{value} ms"


class Command(BaseCommand):
    help = "LLM sarfi, kechikish va xatolar hisoboti"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--include-eval", action="store_true", help="Baholash (eval) so'rovlarini ham hisobga olish")
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--csv", default="", help="Har bir chat so'rovi izini CSV faylga yozish")

    def handle(self, *args, **opts):
        stats = usage_stats(opts["days"], opts["include_eval"])
        if opts["csv"]:
            self.export_csv(opts["csv"], opts["days"], opts["include_eval"])
        if opts["json"]:
            self.stdout.write(json.dumps(stats, ensure_ascii=False, indent=2, default=str))
            return

        chat, llm = stats["chat"], stats["llm"]
        self.stdout.write(self.style.SUCCESS(f"AI hisoboti: oxirgi {stats['days']} kun"))
        self.stdout.write(f"Chat so'rovlari: {chat['requests']}   natijalar: {chat['outcomes'] or '-'}")
        lat = chat["latency_ms"]
        self.stdout.write(f"Kechikish: o'rtacha {_ms(lat['avg'])}, p50 {_ms(lat['p50'])}, p95 {_ms(lat['p95'])}")
        self.stdout.write(f"So'rov boshiga: {chat['avg_llm_calls'] or '-'} LLM chaqiruvi, {chat['avg_tokens'] or '-'} token")
        self.stdout.write(f"Tasdiqsiz bron urinishlari (to'siq ushlagan): {chat['guard_rejections']}")
        self.stdout.write(f"Tool'lar: {chat['tools'] or '-'}")
        self.stdout.write("")
        self.stdout.write(f"LLM chaqiruvlari: {llm['calls']} (xato: {llm['errors']}, limit: {llm['rate_limited']})")
        self.stdout.write(f"Tokenlar: kirish {llm['prompt_tokens']}, chiqish {llm['completion_tokens']}")
        cost = llm["cost_usd"]
        self.stdout.write("Taxminiy narx: " + (f"${cost:.4f}" if cost is not None
                                              else "noma'lum (.env da LLM_PRICE_INPUT_PER_M va LLM_PRICE_OUTPUT_PER_M yo'q)"))
        for name, node in llm["by_node"].items():
            self.stdout.write(f"  {name:<24} {node['calls']:>5} ta   p95 {_ms(node['latency_ms']['p95']):>10}   "
                              f"token {node['prompt_tokens']}+{node['completion_tokens']}")

    def export_csv(self, path, days, include_eval):
        rows = ChatTrace.objects.filter(created_at__gte=timezone.now() - timedelta(days=days))
        if not include_eval:
            rows = rows.filter(tag="")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["trace_id", "created_at", "tag", "engine", "route", "outcome", "latency_ms", "llm_calls",
                             "prompt_tokens", "completion_tokens", "guard_rejections", "tools"])
            for t in rows.order_by("created_at"):
                writer.writerow([t.trace_id, t.created_at.isoformat(), t.tag, t.engine, t.route, t.outcome,
                                 t.latency_ms, t.llm_calls, t.prompt_tokens, t.completion_tokens,
                                 t.guard_rejections, " ".join(t.tool_names)])
        self.stdout.write(f"CSV yozildi: {path} ({rows.count()} qator)")
