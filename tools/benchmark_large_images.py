"""Fresh-process CPU/RSS measurements; synthetic scaled fixtures, NOT accuracy data.

Run: python tools/benchmark_large_images.py
Optional real public inputs: python tools/benchmark_large_images.py --images a.jpg b.jpg
No private filenames/raw images are written to the report (only case numbers).
"""
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from PIL import Image, ImageOps
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def child(path, manual_crop=None):
    from smart_id_photo.processor import Processor
    from smart_id_photo.config import Config
    process=psutil.Process()
    stop=threading.Event(); samples=[process.memory_info().rss]
    def sample():
        while not stop.wait(.005): samples.append(process.memory_info().rss)
    sampler=threading.Thread(target=sample);sampler.start()
    try:
        before=hashlib.sha256(path.read_bytes()).hexdigest()
        started=time.perf_counter()
        with tempfile.TemporaryDirectory() as directory:
            result=Processor().process(path,Config(output_dir=directory,max_kb=50),manual_crop)
            report={'status':result.status,'reasons':result.reasons,
                    'crop':result.crop,'geometry':asdict(result.geometry),
                    'image_info':None if result.image_info is None else asdict(result.image_info),
                    'output_bytes':result.bytes,'jpeg_quality':result.jpeg_quality,
                    'wall_seconds':time.perf_counter()-started,
                    'source_preserved':before==hashlib.sha256(path.read_bytes()).hexdigest()}
            report['manual_crop_used']=manual_crop is not None
            report['engine_peak_sampled_rss_bytes']=max(samples)
            # Independent full-resolution pixel path for same MANUAL rectangle.
            # This isolates resampling effects; it is NOT head/hair ground truth.
            if result.crop and result.output:
                from smart_id_photo.image_loader import load_image_details
                from smart_id_photo.compressor import encode_jpeg
                from io import BytesIO
                # Benchmark-only budget removes the working shrink for comparison.
                # No production Config or its validations are changed.
                from types import SimpleNamespace
                reference_config=SimpleNamespace(max_input_bytes=33_554_432,max_pixels=40_000_000,
                                                 max_working_pixels=40_000_000)
                full,_,_=load_image_details(path,reference_config)
                try:
                    with full.crop(result.crop) as crop:
                        data,quality=encode_jpeg(crop,Config(max_kb=50))
                    with Image.open(BytesIO(data)) as reference, Image.open(result.output) as actual:
                        a=np.asarray(actual,dtype=np.float32);b=np.asarray(reference,dtype=np.float32)
                        mse=float(np.mean((a-b)**2));mae=float(np.mean(np.abs(a-b)))
                        report['same_rectangle_full_resolution_comparison']={
                            'mean_absolute_rgb_error_0_255':mae,'mse':mse,
                            'psnr_db':None if mse==0 else 10*math.log10(255**2/mse),
                            'identical_decoded_pixels':mse==0,'reference_jpeg_quality':quality,
                            'comparison_quality':result.jpeg_quality,
                            'meaning':'Numerical resampling difference; not human quality or crop accuracy'}
                finally:full.close()
    finally:
        stop.set();sampler.join()
    report['peak_sampled_rss_bytes_including_reference_comparison']=max(samples)
    # ru_maxrss captures native allocator peaks; Linux KiB, macOS bytes.
    import resource
    high=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report['process_high_water_rss_bytes_including_reference_comparison']=int(high if sys.platform=='darwin' else high*1024)
    print(json.dumps(report))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--child')
    parser.add_argument('--images',nargs='*')
    parser.add_argument('--manual-crop',nargs=4,type=int)
    args=parser.parse_args()
    if args.child:
        child(Path(args.child),args.manual_crop);return
    cases=[]
    with tempfile.TemporaryDirectory() as directory:
        if args.images:
            cases=[(f'public_input_{i+1}',Path(path),'Provided source; provenance not inferred')
                   for i,path in enumerate(args.images)]
        else:
            for name,size,fmt in [('synthetic_29mp_jpeg',(4480,6536),'JPEG'),
                                  ('synthetic_40mp_jpeg',(8000,5000),'JPEG'),
                                  ('synthetic_40mp_png',(8000,5000),'PNG')]:
                path=Path(directory)/(name+('.jpg' if fmt=='JPEG' else '.png'))
                with Image.open(ROOT/'examples/astronaut.png') as base:
                    # Deliberately scaled test data: no claim of real 40MP detail.
                    with base.resize(size,Image.Resampling.LANCZOS) as image:image.save(path,fmt)
                cases.append((name,path,'Public NASA astronaut image scaled solely for resource testing'))
        reports=[]
        for name,path,provenance in cases:
            command=[sys.executable,__file__,'--child',str(path)]
            if args.manual_crop:
                command+=['--manual-crop',*[str(v) for v in args.manual_crop]]
            completed=subprocess.run(command,
                                     check=True,text=True,capture_output=True)
            report=json.loads(completed.stdout)
            report['case']=name;report['fixture_provenance']=provenance
            reports.append(report)
            print(name,report['status'],report['wall_seconds'],flush=True)
    result={'version':'0.2.0','platform':platform.platform(),'python':sys.version,
            'worker_count':1,'sampling_interval_seconds':.005,
            'available_ram_bytes_at_end':psutil.virtual_memory().available,
            'accuracy_validated':False,'cases':reports}
    name='large-manual-reference.json' if args.manual_crop else (
        'large-public-inputs.json' if args.images else 'large-input-benchmark.json')
    destination=ROOT/'reports'/name
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(destination)


if __name__=='__main__':main()
