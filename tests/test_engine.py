from io import BytesIO
import hashlib
from dataclasses import replace
from PIL import Image
import numpy as np
import pytest
from smart_id_photo.config import Config, mm_to_pixels
from smart_id_photo.compressor import encode_jpeg
from smart_id_photo.crop_optimizer import optimize_crop, validate_manual
from smart_id_photo.schema import Geometry
from smart_id_photo.head_locator import estimate_head
from smart_id_photo.image_loader import load_image
from smart_id_photo.processor import Processor


class FixedDetector:
    def __init__(self, faces): self.faces = faces
    def detect(self, image, config): return Geometry(faces=self.faces)


@pytest.mark.parametrize("key,value", [("backend","cloud"),("width",0),("width",True),("max_kb",-1),("kb_bytes",1000),("quality_floor",96),("max_pixels",40_000_001),("max_working_pixels",24_000_001)])
def test_config_rejects_unsafe_settings(key,value):
    with pytest.raises(ValueError): Config(**{key:value})


def test_mm():
    assert (mm_to_pixels(25), mm_to_pixels(35)) == (295,413)


@pytest.mark.parametrize("kb", [15,20,30,50,100])
def test_real_jpeg_dimensions_size_color_and_metadata(kb):
    data, quality = encode_jpeg(Image.new("RGB",(500,800),"wheat"), Config(max_kb=kb))
    assert len(data) <= kb*1024 and quality >= 65
    with Image.open(BytesIO(data)) as image:
        image.load()
        assert image.size == (295,413) and image.mode == "RGB"
        assert image.info.get("icc_profile")
        assert image.info["dpi"] == (300,300)


def test_impossible_compression():
    image = Image.fromarray(np.random.default_rng(42).integers(0,256,(1000,1000,3),dtype=np.uint8))
    with pytest.raises(ValueError, match="quality floor"):
        encode_jpeg(image, Config(width=1000,height=1000,max_kb=20))


def test_compression_reduces_quality_to_meet_real_budget():
    image = Image.fromarray(np.random.default_rng(7).integers(0,256,(413,295,3),dtype=np.uint8))
    data, quality = encode_jpeg(image, Config(max_kb=100,quality_floor=20))
    assert 20 <= quality < 95 and len(data) <= 100*1024
    # The chosen quality must be the highest permitted integer quality.
    # Independently encode the next integer quality and check actual bytes.
    profile = Image.open(BytesIO(data)).info['icc_profile']
    buf=BytesIO()
    image.save(buf,'JPEG',quality=quality+1,subsampling=0,optimize=False,dpi=(300,300),icc_profile=profile)
    assert len(buf.getvalue()) > 100*1024


def test_crop_retains_estimate_and_matches_ratio():
    config = Config()
    g = estimate_head(Geometry(faces=[(350,300,200,220)]))
    rect, reasons = optimize_crop((1000,1200),g,config)
    assert not reasons
    l,t,r,b = g.estimated_head
    assert rect[0] <= l and rect[1] <= t and rect[2] >= r and rect[3] >= b
    assert abs((rect[2]-rect[0])/(rect[3]-rect[1])-295/413) < .005


def test_head_outside_source_is_flagged():
    g = estimate_head(Geometry(faces=[(0,0,100,100)]))
    rect, reasons = optimize_crop((200,250),g,Config())
    assert reasons and rect[0] >= 0 and rect[1] >= 0


@pytest.mark.parametrize("rect", [(-1,0,295,413),(0,0,900,413),(0,0,200,413),(0,0,float('nan'),413)])
def test_manual_invalid(rect):
    with pytest.raises(ValueError): validate_manual(rect,(500,600),Config())


def test_original_preserved_and_unique_exports(tmp_path):
    source = tmp_path/'照片.jpg'
    Image.new('RGB',(500,600),'white').save(source)
    before = hashlib.sha256(source.read_bytes()).digest()
    engine = Processor(FixedDetector([(160,160,120,120)]))
    cfg = Config(output_dir=str(tmp_path))
    a,b = engine.process(source,cfg),engine.process(source,cfg)
    assert a.status == b.status == 'REVIEW'
    assert a.output != b.output
    assert hashlib.sha256(source.read_bytes()).digest() == before


@pytest.mark.parametrize("faces", [[],[(10,10,70,70),(140,10,70,70)]])
def test_no_or_multiple_faces_not_silently_cropped(tmp_path,faces):
    source = tmp_path/'in.png'
    Image.new('RGB',(500,600)).save(source)
    result = Processor(FixedDetector(faces)).process(source,Config(output_dir=str(tmp_path)))
    assert result.status == 'REVIEW' and result.output is None and result.preview


def test_manual_rescues_detection_failure_but_stays_review(tmp_path):
    source = tmp_path/'in.png'
    Image.new('RGB',(500,600)).save(source)
    result = Processor(FixedDetector([])).process(source,Config(output_dir=str(tmp_path)),(0,0,295,413))
    assert result.status == 'REVIEW' and result.output and result.manual


def test_invalid_and_oversize_isolated(tmp_path):
    source = tmp_path/'in.jpg'
    source.write_bytes(b'bad jpeg')
    assert Processor(FixedDetector([])).process(source,Config()).status == 'FAIL'
    Image.new('RGB',(100,100)).save(source)
    with pytest.raises(ValueError,match='pixel limit'): load_image(source,Config(max_pixels=9999))


def test_exif_orientation_and_transparency(tmp_path):
    path=tmp_path/'rotated.jpg'
    exif=Image.Exif(); exif[274]=6
    Image.new('RGB',(120,80),'red').save(path,exif=exif)
    image,notes=load_image(path,Config())
    assert image.size == (80,120) and not image.getexif().get(274)
    path=tmp_path/'alpha.png'
    Image.new('RGBA',(20,20),(255,0,0,0)).save(path)
    image,notes=load_image(path,Config())
    assert image.getpixel((0,0)) == (255,255,255) and notes


def test_offline_real_detector(monkeypatch,tmp_path):
    import socket
    def deny(*args,**kwargs): raise AssertionError('Outbound network forbidden')
    monkeypatch.setattr(socket.socket,'connect',deny)
    monkeypatch.setattr(socket.socket,'connect_ex',deny)
    monkeypatch.setattr(socket,'create_connection',deny)
    from skimage.data import astronaut
    source=tmp_path/'astronaut.png'
    Image.fromarray(astronaut()).save(source)
    result=Processor().process(source,Config(output_dir=str(tmp_path)))
    assert len(result.geometry.faces) == 1 and result.output and result.status == 'REVIEW'


def test_ui_construction():
    from smart_id_photo.ui.app import build_app
    app=build_app()
    assert app.analytics_enabled is False
