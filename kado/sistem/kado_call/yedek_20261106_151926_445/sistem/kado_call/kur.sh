#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v node >/dev/null || { echo 'Ubuntu icinde Node.js bulunamadi. Dun kullandigin Ubuntu terminalinde calistirin.'; exit 1; }
roots=("$HOME")
for folder in /mnt/c/KADO /mnt/c/Users/user/Downloads; do [[ ! -d "$folder" ]] || roots+=("$folder"); done
mapfile -t found < <(find "${roots[@]}" -maxdepth 6 -type f -name bridge.mts -not -path '*/node_modules/*' 2>/dev/null)
candidates=()
for file in "${found[@]}"; do
  folder="$(dirname -- "$file")"
  if [[ -d "$folder/node_modules/baileys-caller" ]]; then candidates+=("$folder"); fi
done
if [[ ${#candidates[@]} -eq 1 ]]; then
  target_dir="${candidates[0]}"
else
  echo 'Dun arama yaptigin kado-call klasorunun Ubuntu yolunu gir.'
  if [[ ${#candidates[@]} -gt 0 ]]; then printf 'Bulunan klasor: %s\n' "${candidates[@]}"; fi
  read -r -p 'Klasor yolu (ornek /home/kullanici/kado-call): ' target_dir
fi
[[ -d "$target_dir/node_modules/baileys-caller" ]] || { echo 'Bu klasorde dun kurulan baileys-caller bulunamadi. Hicbir sey degistirilmedi.'; exit 1; }
# Existing bridge.mts, package.json, auth and node_modules are kept.
for file in kado-native-call.mts live-feeder.mjs patch-sdk.mjs; do cp -- "$source_dir/$file" "$target_dir/$file"; done
cd -- "$target_dir"
node patch-sdk.mjs
node - "$target_dir" "$source_dir/location.json" "$source_dir/link.json" <<'JS'
const fs=require('fs');
fs.writeFileSync(process.argv[3],JSON.stringify({directory:process.argv[2],link_file:process.argv[4],distro:process.env.WSL_DISTRO_NAME||''},null,2));
JS
echo 'Arama adaptoru hazir. Eski bridge.mts ve auth klasoru korundu.'
echo 'Artik asil Kadoya numarasini soyleyerek WhatsApp aramasi yaptirabilirsin.'
