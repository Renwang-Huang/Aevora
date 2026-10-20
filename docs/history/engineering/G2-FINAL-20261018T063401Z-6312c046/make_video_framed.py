from audit import *
out=E/'final/video-framed';out.mkdir(exist_ok=False);v=json.loads((E/'final/browser-framed/RESULT.json').read_text());assert v['status']=='PASS' and len(v['checks'])==10 and not v['errors'];source=Path(v['video']);target=out/'aevora-gen2-decision-journey.mp4'
assert record('encode-framed-browser-video',['ffmpeg','-n','-i',source,'-c:v','libx264','-preset','medium','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',target])==0
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',target]));duration=float(probe['format']['duration']);assert 120<=duration<=240
srt=[]
def stamp(value):
 n=round(value*1000);return f'{n//3600000:02d}:{n//60000%60:02d}:{n//1000%60:02d},{n%1000:03d}'
for i,a in enumerate(v['actions']):
 end=v['actions'][i+1]['seconds'] if i+1<len(v['actions']) else duration
 srt.append(f'{i+1}\n{stamp(a["seconds"])} --> {stamp(min(end,duration))}\n{a["action"]}\n')
(out/'captions.srt').write_text('\n'.join(srt));(out/'WALKTHROUGH.md').write_text((P/'docs/DEMO_WALKTHROUGH.md').read_text())
assert record('framed-video-contact-frame',['ffmpeg','-n','-ss','55','-i',target,'-frames:v','1',out/'actual-frame-55s.png'])==0
write(out/'VIDEO_RECEIPT.json',dict(status='PASS',source_webm=str(source.relative_to(E)),source_sha256=sha(source),mp4=str(target.relative_to(E)),mp4_sha256=sha(target),mp4_bytes=target.stat().st_size,duration_seconds=duration,frame_size=[probe['streams'][0]['width'],probe['streams'][0]['height']],captions_sha256=sha(out/'captions.srt'),browser_trace_sha256=sha(E/'final/browser-framed/browser-trace.zip'),model_execution=False,actual_recording='Unedited real Playwright browser frames; MP4 is format re-encoding only. SRT is a separate optional narration tied to actual action times.',hosted_video_url='USER_ACTION_REQUIRED'))
print(json.dumps(json.loads((out/'VIDEO_RECEIPT.json').read_text()),indent=2))
