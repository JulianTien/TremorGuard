#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$ROOT/output/neuro-pulse-showcase"
HTML_DIR="$OUTPUT_DIR/html"
SITE_URL="https://parkinson.zeabur.app/"

export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"

latest_cli_screenshot() {
  ls -t "$ROOT"/.playwright-cli/page-*.png | head -1
}

save_latest_screenshot() {
  local filename="$1"
  mv "$(latest_cli_screenshot)" "$OUTPUT_DIR/$filename"
}

python3 "$ROOT/scripts/generate_neuro_pulse_showcase.py"
mkdir -p "$OUTPUT_DIR"

"$PWCLI" open "$SITE_URL"
"$PWCLI" resize 1920 1080
"$PWCLI" screenshot >/dev/null
save_latest_screenshot "neuro-pulse-01-home-hero.png"

"$PWCLI" goto "$SITE_URL" >/dev/null
"$PWCLI" eval '() => new Promise((resolve) => {
  const section = document.querySelector("main > div:nth-of-type(2)");
  if (section) {
    const top = section.getBoundingClientRect().top + window.scrollY - 90;
    window.scrollTo(0, Math.max(top, 0));
  }
  setTimeout(() => resolve(window.scrollY), 600);
})' >/dev/null
"$PWCLI" screenshot >/dev/null
save_latest_screenshot "neuro-pulse-02-feature-cards.png"

"$PWCLI" goto "$SITE_URL" >/dev/null
"$PWCLI" eval '() => new Promise((resolve) => {
  const slider = document.querySelector("input[type=range]");
  if (slider) {
    slider.value = "3";
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    slider.dispatchEvent(new Event("change", { bubbles: true }));
  }
  const section = document.querySelector("main > div:nth-of-type(3)");
  if (section) {
    const top = section.getBoundingClientRect().top + window.scrollY - 90;
    window.scrollTo(0, Math.max(top, 0));
  }
  setTimeout(() => resolve(slider ? slider.value : "missing"), 600);
})' >/dev/null
"$PWCLI" screenshot >/dev/null
save_latest_screenshot "neuro-pulse-03-severity-demo.png"

for html_name in \
  neuro-pulse-04-ai-chat-backend \
  neuro-pulse-05-rehab-guidance-backend \
  neuro-pulse-06-dashboard-analytics-backend
do
  "$PWCLI" goto "file://$HTML_DIR/$html_name.html" >/dev/null
  "$PWCLI" screenshot >/dev/null
  save_latest_screenshot "$html_name.png"
done

"$PWCLI" close >/dev/null
