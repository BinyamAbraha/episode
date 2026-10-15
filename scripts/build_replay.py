"""Build a read-only, self-contained public replay from verified local evidence."""

import sys, json, shutil, html
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from episode.storage import root, source_root, connect, rows, now, canonical, digest
from episode.service import episode, version, media_path
from episode.media import command
from episode.analysis import list_analyses
from episode.fixtures import demonstrations

r = Path(__file__).resolve().parents[1]
out = root() / "evidence/replay"
out.mkdir(exist_ok=True)
with connect() as db:
    verified = rows(db, "SELECT * FROM verifications ORDER BY id")
record = next(
    (v for v in reversed(verified) if json.loads(v["result"])["episodes"] < 50),
    verified[-1],
)
manifest = version(record["version"])
e = episode(0)
payload = {
    "generated": now(),
    "version_id": record["version"],
    "manifest": manifest,
    "verification": json.loads(record["result"]),
    "episode": e,
    "fault_fixtures": demonstrations(),
    "mode": "Recorded read-only replay; no live jobs, reviews or version creation",
}
analysis_record = next((a for a in list_analyses(0) if a["mode"] == "vlm"), None)
if analysis_record:
    payload["analysis"] = analysis_record
    analysis_dir = root() / "derived/analysis" / analysis_record["id"]
    shutil.copy2(analysis_dir / "contact-sheet.png", out / "analysis-contact-sheet.png")
transform = []
for c in e["cameras"]:
    source = media_path(e["metadata"], c["key"])
    dest = out / (c["label"] + ".webm")
    args = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-threads",
        "2",
        "-ss",
        str(c["offset"]),
        "-i",
        str(source),
        "-t",
        str(e["duration"]),
        "-an",
        "-c:v",
        "libvpx-vp9",
        "-threads",
        "2",
        "-deadline",
        "realtime",
        "-cpu-used",
        "6",
        "-crf",
        "34",
        "-b:v",
        "0",
        str(dest),
    ]
    command(args, timeout=90)
    transform.append(
        {
            "source_sha256": digest(source),
            "output_sha256": digest(dest),
            "source_offset": c["offset"],
            "duration": e["duration"],
            "settings": args[args.index("-an") : -1],
            "time_mapping": "clip PTS plus source offset equals source video PTS",
        }
    )
(out / "record.json").write_text(json.dumps(payload, indent=2) + "\n")
(out / "transforms.json").write_text(json.dumps(transform, indent=2) + "\n")
shutil.copy2(r / "web/src/style.css", out / "style.css")
shutil.copy2(source_root() / "README.md", out / "SOURCE_CARD.md")
license_path = r / "LICENSE"
shutil.copy2(license_path, out / "LICENSE")
(out / "ATTRIBUTION.txt").write_text(
    "Source recordings: lerobot/svla_so101_pickplace, revision "
    + manifest["source"]["revision"]
    + ". Dataset card declares Apache-2.0. Original dataset: https://huggingface.co/datasets/lerobot/svla_so101_pickplace\nModifications: episode 0 extracted and transcoded from AV1 to VP9/WebM. Signal data is unchanged. See transforms.json for input/output hashes and settings. No publisher endorsement is implied.\n"
)
(out / "index.html").write_text(
    """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Episode | Recorded inspection replay</title><link rel="stylesheet" href="style.css"><style>main{max-width:1200px;margin:auto}.replay-banner{overflow-wrap:anywhere;background:#172b2a;color:white;padding:16px 28px}.replay-banner p{color:#e1ece4;margin:4px 0}.replay-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0}.cameras video{aspect-ratio:4/3;width:100%}.record code{display:block}#message{color:#172b2a}#splits p,#analysis p{overflow-wrap:anywhere}.step{display:none}.step.active{display:block}svg{width:100%;background:white;border:1px solid #c8d1cb}#status{padding:10px 0}footer a{color:#116457}</style><header class="top"><a class="brand" href="index.html">EPISODE<span>Robotics data workbench</span></a><span class="local">RECORDED REPLAY</span></header><div class="replay-banner"><strong>Read-only recorded data. No live processing.</strong><p id="source">Loading source version and generation time…</p></div><main><div class="eyebrow">PINNED RECORDINGS / REPRODUCIBLE CURATION</div><h1>Episode inspection and recorded dataset verification.</h1><p>This replay shows actual recordings and saved verification evidence from the local application. Review and publication below are recorded results.</p><div class="replay-tabs" role="group" aria-label="Replay sections"><button data-tab="inspect">1. Inspect recording</button><button data-tab="quality">2. Explain a finding</button><button data-tab="review">3. Recorded curation</button><button data-tab="verify">4. Consumer evidence</button></div><section id="inspect" class="step active"><h2>Episode 0: pink lego brick into the transparent box</h2><div class="cameras"><div class="camera"><div class="camera-label">SIDE / SOURCE CAMERA</div><video id="side" src="side.webm" muted playsinline preload="auto" aria-label="Side camera recording"></video></div><div class="camera"><div class="camera-label">UP / SOURCE CAMERA</div><video id="up" src="up.webm" muted playsinline preload="auto" aria-label="Up camera recording"></video></div></div><div class="transport"><button id="play">Play recording</button><button id="previous">Previous sample</button><button id="next">Next sample</button><span id="cursor" class="mono"></span></div><label>Episode time<input type="range" id="seek" min="0" step="0.03333333333333333" aria-label="Episode time"></label><p>Shared cursor uses recorded offsets. Browser seeks are approximate; physical camera synchronization is undocumented.</p><h2>Shoulder pan: state and action</h2><svg id="plot" viewBox="0 0 900 170" role="img" aria-label="State and action signal curves; numeric sample values follow"></svg><div id="numeric" class="table-wrap"></div></section><section id="quality" class="step"><h2>Injected timestamp gap</h2><div class="notice">Controlled deterministic fixture. This is not a defect discovered in the source recording.</div><p>The fixture inserts 0.2 seconds into the second half of a nominal 30 Hz sequence. Rule <code>time.gap</code> compares adjacent timestamps against 1.5 nominal sample periods, or 0.05 seconds.</p><p id="fault-evidence"></p><p>The original dataset produced no findings under the implemented release rules. That does not prove task success or physical synchronization.</p></section><section id="review" class="step"><h2>Recorded dataset version</h2><p>This recorded curated version freezes selected episode identities, demonstration reviews and interval annotations. Its exact membership appears below. Subsequent reviews do not mutate this manifest.</p><div id="splits" class="record"></div><p>Exact state/action sequence families stay together. Session identity is unknown. No session-level separation or exhaustive near-duplicate detection is claimed.</p><a href="record.json">Inspect the recorded manifest and evidence</a></section><section id="verify" class="step"><h2>Executed consumer verification</h2><div id="verification" class="record"></div><p>The consumer reads preserved Parquet and decodes original AV1 images. The preview clips shown here are separate VP9 derivatives. A pinned LeRobot reader and robot task-success evaluation were not executed.</p><a href="transforms.json">Preview transformation records</a></section><p id="status" role="status"></p></main><footer>Source: <a href="https://huggingface.co/datasets/lerobot/svla_so101_pickplace">lerobot/svla_so101_pickplace</a> · <a href="ATTRIBUTION.txt">Attribution</a> · <a href="LICENSE">Apache-2.0</a>. Built with AI assistance; results reflect executed local checks.</footer><script src="replay.js"></script></html>"""
)
(out / "replay.js").write_text(
    """const el=id=>document.getElementById(id);let record;fetch('record.json').then(r=>{if(!r.ok)throw Error('Recorded data unavailable');return r.json()}).then(r=>{record=r;const fault=r.fault_fixtures.find(f=>f.name==='timestamp gap').findings.find(f=>f.rule==='time.gap');el('fault-evidence').textContent=`Observed gap: ${fault.observed.toFixed(6)} seconds. Severity: ${fault.severity}. Threshold: ${fault.threshold.toFixed(6)} seconds. Consumer windows spanning the gap are rejected, without interpolation.`;el('source').textContent=`Source version ${r.version_id} · Generated ${r.generated}`;el('seek').max=r.episode.duration-1/30;el('splits').innerHTML=`<strong>${r.manifest.name}</strong><code>${r.version_id}</code>`;for(const [name,ids] of Object.entries(r.manifest.split.membership)){const p=document.createElement('p');p.textContent=`${name}: ${ids.length} episodes (${ids.join(', ')})`;el('splits').append(p)}const annotation=document.createElement('p');annotation.textContent=`Frozen annotation revisions: ${r.manifest.annotations.length}. Example: ${r.manifest.annotations[0]?.label||'none'}. Review outcomes remain unknown.`;el('splits').append(annotation);const v=r.verification;el('verification').textContent=`${v.status}: ${v.episodes} episodes, ${v.validated_signal_windows} signal windows, ${v.decoded_images} decoded images. Elapsed ${v.seconds.toFixed(2)} seconds. Images [1,2,4,480,640,3]; state/action [1,4,6]. ${v.decoded_window_policy}. Cache: ${v.cache_condition}.`;render(0)}).catch(e=>el('status').textContent=e.message);const videos=[el('side'),el('up')];function render(t){if(!record)return;const data=record.episode.samples;const s=data.reduce((a,b)=>Math.abs(b.timestamp-t)<Math.abs(a.timestamp-t)?b:a);el('cursor').textContent=`${t.toFixed(2)} / ${record.episode.duration.toFixed(2)} s`;el('seek').value=t;const all=data.flatMap(s=>[s['observation.state'][0],s.action[0]]),lo=Math.min(...all),hi=Math.max(...all),span=hi-lo||1;let svg='';for(const [key,color] of [['observation.state','#116457'],['action','#9a4c20']]){let path=data.map((s,i)=>`${i?'L':'M'} ${20+s.timestamp/record.episode.duration*860} ${140-(s[key][0]-lo)/span*120}`).join(' ');svg+=`<path d="${path}" fill="none" stroke="${color}" stroke-width="2"/>`}const x=20+t/record.episode.duration*860;el('plot').innerHTML=svg+`<line x1="${x}" x2="${x}" y1="10" y2="150" stroke="#172b2a"/>`;el('numeric').innerHTML='<table><thead><tr><th scope="col">Feature</th><th scope="col">State</th><th scope="col">Action</th></tr></thead><tbody>'+record.episode.info.features['observation.state'].names.map((n,i)=>`<tr><th scope="row">${n}</th><td>${s['observation.state'][i].toFixed(3)}</td><td>${s.action[i].toFixed(3)}</td></tr>`).join('')+'</tbody></table>'}function seek(t){if(!record)return;t=Math.max(0,Math.min(record.episode.duration-1/30,t));videos.forEach(v=>{v.pause();v.currentTime=t});el('play').textContent='Play recording';render(t)}el('seek').oninput=e=>seek(Number(e.target.value));el('previous').onclick=()=>seek(Number(el('seek').value)-1/30);el('next').onclick=()=>seek(Number(el('seek').value)+1/30);el('play').onclick=()=>{if(videos[0].paused){videos.forEach(v=>v.play().catch(e=>el('status').textContent=e.message));el('play').textContent='Pause recording'}else{videos.forEach(v=>v.pause());el('play').textContent='Play recording'}};videos[0].ontimeupdate=()=>{if(videos[0].paused)return;render(videos[0].currentTime);if(Math.abs(videos[1].currentTime-videos[0].currentTime)>.08)videos[1].currentTime=videos[0].currentTime};videos[0].onended=()=>el('play').textContent='Play recording';document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{videos.forEach(v=>v.pause());el('play').textContent='Play recording';document.querySelectorAll('.step').forEach(s=>s.classList.toggle('active',s.id===b.dataset.tab));el('status').textContent=b.textContent+' · recorded read-only evidence'});"""
)
# Append a recorded analysis section without any simulated mutation controls.
if analysis_record:
    page = (out / "index.html").read_text()
    page = page.replace(
        '<button data-tab="verify">4. Consumer evidence</button>',
        '<button data-tab="verify">4. Consumer evidence</button><button data-tab="analysis">5. Recorded model suggestions</button>',
    )
    section = '<section id="analysis" class="step"><h2>Recorded local model suggestions</h2><p>These are unverified model hypotheses from sparse recorded frames. No live inference or review occurs in this replay. No human semantic accuracy or review-time savings have been measured.</p><p id="analysis-source"></p><img src="analysis-contact-sheet.png" alt="Recorded contact sheet: two camera views at four labelled episode times" style="width:100%;height:auto"><div id="analysis-suggestions"></div><details><summary>Recorded model provenance and response</summary><pre id="analysis-provenance" tabindex="0" aria-label="Recorded analysis JSON"></pre></details></section>'
    page = page.replace(
        '<p id="status" role="status">', section + '<p id="status" role="status">'
    )
    (out / "index.html").write_text(page)
    js = (out / "replay.js").read_text()
    extra = """const a=r.analysis;if(a){el('analysis-source').textContent=`Analysis ${a.id} · Recorded ${a.created} · Model ${a.result.model.repository} at ${a.result.model.revision}`;el('analysis-provenance').textContent=JSON.stringify(a.result,null,2);for(const s of a.suggestions){const article=document.createElement('article');article.className='record';const h=document.createElement('h3');h.textContent=`Suggested ${s.body.label}: ${s.body.start.toFixed(2)} to ${s.body.end.toFixed(2)} s`;const p=document.createElement('p');p.textContent=s.body.explanation+' Evidence: '+s.body.evidence.join(', ')+'. Review required.';article.append(h,p);el('analysis-suggestions').append(article)}}"""
    js = js.replace("record=r;const fault=", "record=r;" + extra + "const fault=")
    (out / "replay.js").write_text(js)
    with (out / "ATTRIBUTION.txt").open("a") as f:
        f.write(
            "Analysis image: original frames resized with Lanczos and arranged into a labelled contact sheet. Model: "
            + analysis_record["result"]["model"]["repository"]
            + " at "
            + analysis_record["result"]["model"]["revision"]
            + "; model card declares Apache-2.0. Analysis and frame hashes are retained in record.json. Model suggestions are not human-verified labels.\n"
        )
print(out)
