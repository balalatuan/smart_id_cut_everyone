"""Launch real Gradio HTTP server, permit only loopback socket connections."""
import os
os.environ['GRADIO_ANALYTICS_ENABLED']='False'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['NO_PROXY']=','.join(filter(None,[os.environ.get('NO_PROXY',''),'127.0.0.1','localhost','::1']))
import socket
import ipaddress
import json
from pathlib import Path
import tempfile
import httpx

blocked=[]
original=socket.socket.connect
original_ex=socket.socket.connect_ex
def guard(func):
    def connect(sock,address):
        if sock.family in (socket.AF_INET,socket.AF_INET6):
            host=address[0]
            try: local=ipaddress.ip_address(host).is_loopback
            except ValueError: local=host=='localhost'
            if not local:
                blocked.append(host)
                raise RuntimeError('Remote network blocked in offline UI test')
        return func(sock,address)
    return connect
socket.socket.connect=guard(original)
socket.socket.connect_ex=guard(original_ex)

from smart_id_photo.ui.app import build_app
from gradio_client import Client, handle_file
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    app=build_app(directory)
    try:
        app.queue(max_size=2,default_concurrency_limit=1).launch(
            server_name='127.0.0.1',server_port=7861,share=False,quiet=True,
            prevent_thread_lock=True,allowed_paths=[directory],max_file_size='32mb')
        with httpx.Client(trust_env=False) as http:
            assert http.get('http://127.0.0.1:7861/').status_code==200
            config=http.get('http://127.0.0.1:7861/config').json()
            assert config['analytics_enabled'] is False
            assert 'fonts.googleapis.com' not in json.dumps(config)
        client=Client('http://127.0.0.1:7861',verbose=False)
        values=client.predict(handle_file(str(root/'examples'/'astronaut.png')),
                              'standard',295,413,50,False,0,0,295,413,api_name='/process')
        result=values[2]
        assert result['status']=='REVIEW' and result['bytes'] <= 51200
        assert Path(values[3]).is_file()
        from PIL import Image
        large=Path(directory)/'synthetic-29mp.jpg'
        with Image.new('RGB',(4480,6536),'wheat') as image:
            image.save(large,'JPEG')
        # Synthetic solid raster tests plumbing/limits, not detector accuracy.
        large_values=client.predict(handle_file(str(large)),
                              'standard',295,413,15,True,1000,800,2770,3278,api_name='/process')
        large_result=large_values[2]
        assert large_result['status']=='REVIEW' and large_result['bytes'] <= 15*1024
        assert large_result['image_info']['downsampled'] is True
        assert large_result['image_info']['source_size']==[4480,6536]
        assert large_result['crop']==[1000,800,2770,3278]
        assert Path(large_values[3]).is_file()
        assert '4055' in large_values[4]
        assert not blocked, f'Unintended outbound attempts: {blocked}'
        report={'local_http_status':200,'real_upload_and_processing':True,
                'download_verified':True,'blocked_remote_attempts':len(blocked),
                'test_scope':'Python socket connect/connect_ex guard; no browser packet capture',
                'version':'0.2.0','status':result['status'],'output_bytes':result['bytes'],
                'large_input_29mp_and_15kb_verified':True,
                'large_case_output_bytes':large_result['bytes']}
        (root/'reports'/'ui-offline-smoke-v0.2.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    finally:
        app.close()
