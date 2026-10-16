from dataclasses import replace
import hashlib
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageCms
import numpy as np
import pytest
from smart_id_photo.config import Config
from smart_id_photo.image_loader import load_image_details, bounded_size
from smart_id_photo.processor import Processor
from smart_id_photo.schema import Geometry
from smart_id_photo.coordinates import source_rect_to_working, working_rect_to_source


class FixedDetector:
    def detect(self, image, config):
        # Stable test geometry IN WORKING COORDINATES; not an accuracy evaluation.
        return Geometry(faces=[(round(image.width*.35), round(image.height*.22),
                                round(image.width*.25), round(image.height*.25))])


@pytest.mark.parametrize('size',[(4480,6536),(8000,5000),(1,40_000_000),(40_000_000,1),(5011,7982)])
def test_target_budget_and_no_upscale(size):
    target=bounded_size(size,24_000_000)
    assert target[0]*target[1] <= 24_000_000
    assert target[0] <= size[0] and target[1] <= size[1]


@pytest.fixture(scope='module')
def large_sources(tmp_path_factory):
    directory=tmp_path_factory.mktemp('large-inputs')
    paths={}
    for name,size,fmt in [('29mp.jpg',(4480,6536),'JPEG'),
                          ('40mp.jpg',(8000,5000),'JPEG'),
                          ('40mp.png',(8000,5000),'PNG'),
                          ('over40mp.jpg',(8001,5000),'JPEG')]:
        path=directory/name
        with Image.new('RGB',size,'wheat') as im:
            im.save(path,fmt)
        paths[name]=path
    return paths


@pytest.mark.parametrize('name',['29mp.jpg','40mp.jpg','40mp.png'])
def test_real_large_input_auto_shrink_preserves_source(large_sources,name):
    path=large_sources[name];before=hashlib.sha256(path.read_bytes()).hexdigest()
    image,notes,info=load_image_details(path,Config())
    try:
        assert info.downsampled and image.width*image.height <= 24_000_000
        assert image.size == info.working_size
        assert info.coordinate_space == 'exif_oriented_source'
        assert notes and 'original preserved' in notes[-1]
        assert info.scale_x < 1 and info.scale_y < 1
        assert hashlib.sha256(path.read_bytes()).hexdigest()==before
        # Native JPEG can't reduce 40 -> 24MP by an arbitrary factor.
        assert info.decoder_size == info.source_size
    finally:
        image.close()


def test_overlimit_rejected_before_pixel_decode(large_sources,monkeypatch):
    from PIL import JpegImagePlugin
    def forbidden(*args,**kwargs):
        raise AssertionError('Overlimit image must not be decoded')
    monkeypatch.setattr(JpegImagePlugin.JpegImageFile,'load',forbidden)
    with pytest.raises(ValueError,match='40,005,000.*40,000,000'):
        load_image_details(large_sources['over40mp.jpg'],Config())


def test_large_crop_coordinates_stay_in_source_space(large_sources,tmp_path):
    path=large_sources['29mp.jpg']
    manual=(1000,800,2770,3278)  # exact 295:413 ratio
    result=Processor(FixedDetector()).process(path,Config(output_dir=str(tmp_path)),manual)
    assert result.status=='REVIEW' and result.output and result.crop==manual
    assert result.image_info.source_size==(4480,6536)
    assert result.image_info.downsampled and result.geometry.faces[0][0] > 1400
    with Image.open(result.output) as output:
        assert output.size==(295,413)
    assert result.bytes <= 50*1024


def test_rotated_source_coordinates_and_native_jpeg_reduction(tmp_path):
    path=tmp_path/'rotated.jpg'
    exif=Image.Exif();exif[274]=6
    with Image.new('RGB',(800,400),'red') as original:original.save(path,exif=exif)
    cfg=Config(max_working_pixels=20_000,output_dir=str(tmp_path))
    image,notes,info=load_image_details(path,cfg)
    try:
        assert info.oriented_source_size==(400,800)
        assert info.decoder_reduced and info.decoder_size==(200,100)
        assert image.width*image.height <= 20_000
        assert not image.getexif().get(274)
        rect=(40,80,360,720)
        mapped=working_rect_to_source(source_rect_to_working(rect,info),info)
        assert mapped==rect
    finally:image.close()
    result=Processor(FixedDetector()).process(path,cfg,(40,100,335,513))
    assert result.status=='REVIEW' and result.crop==(40,100,335,513)
    assert result.image_info.oriented_source_size==(400,800)


def test_old_small_image_pixels_and_crop_unchanged():
    """Frozen Phase 1 export is a true regression oracle, not re-encoded expected data."""
    import json,tempfile
    root=Path(__file__).resolve().parents[1]
    prior=json.loads((root/'reports/preliminary-results.json').read_text())
    prior=next(row for row in prior if row['fixture']=='astronaut')
    with tempfile.TemporaryDirectory() as directory:
        result=Processor().process(root/'examples/astronaut.png',Config(output_dir=directory))
        assert result.output and result.status=='REVIEW'
        # LittleCMS embeds the current date in ICC profiles; compare actual JPEG
        # pixels/quantization rather than treating timestamp bytes as image loss.
        with Image.open(result.output) as actual, Image.open(root/prior['output']) as expected:
            assert actual.size==expected.size and actual.tobytes()==expected.tobytes()
            assert actual.quantization==expected.quantization
            assert actual.info['dpi']==expected.info['dpi']
        assert result.jpeg_quality==prior['jpeg_quality']
        assert tuple(prior['crop'])==result.crop
        assert not result.image_info.downsampled


def test_color_and_alpha_retained_with_resizing(tmp_path):
    path=tmp_path/'alpha.png'
    profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    with Image.new('RGBA',(800,600),(255,0,0,128)) as im: im.save(path,icc_profile=profile)
    image,notes,info=load_image_details(path,Config(max_working_pixels=120_000))
    try:
        assert info.downsampled and image.size==(400,300)
        assert image.getpixel((200,150))==(255,127,127)
        assert any('composited' in n for n in notes)
    finally:image.close()


def test_ui_exposes_15kb_and_preserves_50kb_default():
    from smart_id_photo.ui.app import build_app
    app=build_app()
    dropdown=next(component for component in app.config['components']
                  if component['props'].get('label')=='大小上限（1 KB = 1024 B）')
    assert dropdown['props']['value']==50
    assert [str(label) for label,value in dropdown['props']['choices'] if value==15]==['15']


def test_15kb_impossible_is_fail_with_reason_and_no_jpeg(tmp_path):
    source=tmp_path/'noise.png'
    with Image.fromarray(np.random.default_rng(15).integers(0,256,(413,295,3),dtype=np.uint8)) as im:
        im.save(source)
    result=Processor(FixedDetector()).process(source,Config(max_kb=15,output_dir=str(tmp_path)),(0,0,295,413))
    assert result.status=='FAIL' and result.output is None
    assert any('quality floor' in reason for reason in result.reasons)
    assert not list(tmp_path.glob('*.jpg'))


def test_rotated_manual_crop_contains_requested_source_content(tmp_path):
    # Different colors make a wrong coordinate mapping visible in actual pixels.
    from PIL import ImageDraw
    path=tmp_path/'rotated-content.png'
    with Image.new('RGB',(800,1200),'red') as oriented:
        ImageDraw.Draw(oriented).rectangle((100,100,394,512),fill=(0,240,0))
        with oriented.transpose(Image.Transpose.ROTATE_90) as raw:
            exif=Image.Exif();exif[274]=6
            raw.save(path,exif=exif)
    result=Processor(FixedDetector()).process(
        path,Config(max_working_pixels=120_000,output_dir=str(tmp_path)),(100,100,395,513))
    assert result.output and result.image_info.oriented_source_size==(800,1200)
    with Image.open(result.output) as actual:
        r,g,b=actual.getpixel((147,206))
        assert g>200 and r<40 and b<40
