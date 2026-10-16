"""Reproducible SMALL preliminary set, not an independent accuracy evaluation."""
from pathlib import Path
import sys
import json
import platform
import threading
import time
import importlib.metadata
import psutil
from PIL import Image, ImageEnhance, ImageDraw
from skimage.data import astronaut
from smart_id_photo.config import Config
from smart_id_photo.processor import Processor
from smart_id_photo.exporter import export_csv

root = Path(__file__).resolve().parents[1]
examples, reports = root/'examples', root/'reports'
examples.mkdir(exist_ok=True); reports.mkdir(exist_ok=True)
base = Image.fromarray(astronaut())
variants = {'astronaut':base, 'dim':ImageEnhance.Brightness(base).enhance(.5),
            'bright':ImageEnhance.Brightness(base).enhance(1.5),
            'small':base.resize((256,256)), 'large':base.resize((2048,2048)),
            'blurred':base.resize((128,128)).resize((512,512)),
            'blank':Image.new('RGB',(512,512),'white')}
# Synthetic cartoon deliberately tests failure handling, not face accuracy.
cartoon=Image.new('RGB',(500,600),'lightblue'); d=ImageDraw.Draw(cartoon)
d.ellipse((130,70,370,360),fill='black'); d.ellipse((160,120,340,350),fill='peachpuff')
d.ellipse((195,210,210,225),fill='black'); d.ellipse((290,210,305,225),fill='black')
d.arc((210,250,290,290),0,180,fill='brown',width=4)
d.rectangle((100,360,400,600),fill='navy'); variants['synthetic']=cartoon
for name,im in variants.items(): im.save(examples/f'{name}.png')
(examples/'malformed.jpg').write_bytes(b'not a jpeg')
process=psutil.Process()
rss=[]; stop=threading.Event()
def sample():
    while not stop.wait(.01): rss.append(process.memory_info().rss)
engine=Processor(); start_rss=process.memory_info().rss
thread=threading.Thread(target=sample); thread.start()
results=[]; entries=[]
try:
    for name in [*variants,'malformed']:
        source=examples/(f'{name}.jpg' if name=='malformed' else f'{name}.png')
        before=process.cpu_times(); start=time.perf_counter()
        result=engine.process(source,Config(output_dir=str(root/'output'/'benchmark')))
        after=process.cpu_times()
        entries.append({'fixture':name,'wall_seconds':time.perf_counter()-start,
                        'cpu_seconds':(after.user+after.system)-(before.user+before.system), **result.to_dict()})
        results.append(result)
finally:
    stop.set(); thread.join()
versions={name:importlib.metadata.version(name) for name in
          ['Pillow','numpy','opencv-python-headless','PyYAML','psutil','gradio','scikit-image','pytest']}
environment={'platform':platform.platform(),'python':sys.version,'logical_cpus':psutil.cpu_count(),
             'total_ram_bytes':psutil.virtual_memory().total,'available_ram_bytes':psutil.virtual_memory().available,
             'versions':versions,'worker_count':1,'opencv_threads':1,'sampling_interval_seconds':.01,
             'rss_before_bytes':start_rss,'peak_sampled_rss_bytes':max([start_rss,*rss]),
             'accuracy_validated':False,'independent_people':1,'fixture_count':len(entries)}
(reports/'environment.json').write_text(json.dumps(environment,indent=2),encoding='utf-8')
# Convert absolute result paths to package-relative paths for portable reports.
for entry in entries:
    for key in ['output','preview']:
        if entry.get(key): entry[key]=str(Path(entry[key]).relative_to(root))
(reports/'preliminary-results.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
for result in results:
    if result.output: result.output=str(Path(result.output).relative_to(root))
export_csv(results,reports/'preliminary-results.csv')
print(json.dumps(environment,indent=2))
for entry in entries: print(entry['fixture'],entry['status'],len(entry['geometry']['faces']),entry['bytes'])
