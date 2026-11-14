"""Bounded Studio snapshot inspection and deterministic generated-CAD composition.

No native program is imported or executed. Producer markers are supplied format
claims, never authentication. The preserved marker identifies the source template;
explicit modifier and input hashes identify the newly composed model.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import re
import stat
import struct
import zipfile
import zlib
from xml.etree import ElementTree as ET

QUALIFIED_VERSION = '02.09.01.70'
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_SETTINGS_BYTES = MAX_MODEL_XML_BYTES = 2 * 1024 * 1024
MAX_IMPORT_REQUEST_BYTES = 24 * 1024 * 1024
MAX_SETTINGS_DEPTH = 32
MODIFIER = '3D Printer Agent 0.4.0'
CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
SETTINGS_PATH = 'Metadata/project_settings.config'
MODEL_PATH = '3D/3dmodel.model'
PLATE_BED_PREFIXES = {'Cool Plate':'cool_plate', 'Engineering Plate':'eng_plate',
                      'High Temp Plate':'hot_plate', 'Textured PEI Plate':'textured_plate',
                      'Supertack Plate':'supertack_plate'}
MACHINE_FIELDS = ('printer_model','printer_technology','nozzle_diameter','printable_area',
                  'printable_height','machine_start_gcode','machine_end_gcode')
PROCESS_FIELDS = ('layer_height','initial_layer_print_height','wall_loops','top_shell_layers',
                  'bottom_shell_layers','sparse_infill_density','outer_wall_speed',
                  'inner_wall_speed','sparse_infill_speed','initial_layer_speed')
FILAMENT_FIELDS = ('filament_type','filament_diameter','filament_density','filament_flow_ratio',
                   'filament_max_volumetric_speed','nozzle_temperature','nozzle_temperature_initial_layer')


def _hash(content):
    return hashlib.sha256(content).hexdigest()


def _safe_name(name, directory=False):
    path = name[:-1] if directory and name.endswith('/') else name
    if (not path or len(name)>1024 or '\\' in name or ':' in name
            or any(ord(c)<32 or ord(c)==127 for c in name)
            or any(part in ('','.','..') for part in path.split('/'))):
        raise ValueError('ZIP에 안전한 상대 파일 경로가 필요합니다.')
    name.encode('utf-8')
    return path


def _members(content):
    """Verify inventory, contiguous local records, actual DEFLATE bytes and CRC."""
    if not isinstance(content,bytes) or not 22<=len(content)<=MAX_ARCHIVE_BYTES:
        raise ValueError('프로젝트 ZIP은 비어 있지 않은 16 MiB 이하 파일이어야 합니다.')
    try:
        end=content.rfind(b'PK\x05\x06', max(0,len(content)-65557))
        if end<0 or end+22>len(content):
            raise ValueError('완성된 ZIP 파일이 필요합니다.')
        _,disk,start_disk,disk_count,count,size,offset,comment=struct.unpack_from('<4s4H2IH',content,end)
        if (disk or start_disk or disk_count!=count or not 1<=count<=MAX_ENTRIES
                or end+22+comment!=len(content) or offset+size!=end):
            raise ValueError('ZIP 목록·항목 수·후행 데이터가 올바르지 않습니다. ZIP64/분할 ZIP은 지원하지 않습니다.')
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos=archive.infolist()
            if len(infos)!=count or archive.start_dir!=offset:
                raise ValueError('ZIP 중앙 목록 위치가 다릅니다.')
            # Central entries must occupy the complete declared central directory.
            cursor=offset
            for info in infos:
                if content[cursor:cursor+4]!=b'PK\x01\x02' or cursor+46>end:
                    raise ValueError('ZIP 중앙 목록이 손상되었습니다.')
                n,e,c=struct.unpack_from('<3H',content,cursor+28)
                cursor+=46+n+e+c
            if cursor!=end:
                raise ValueError('ZIP 중앙 목록에 선언되지 않은 데이터가 있습니다.')
            seen={}; result={}; cursor=0; total=0
            for info in sorted(infos,key=lambda item:item.header_offset):
                name=_safe_name(info.orig_filename,info.is_dir())
                mode=stat.S_IFMT(info.external_attr>>16)
                if (name in seen or info.orig_filename!=info.filename
                        or mode not in (0,stat.S_IFREG,stat.S_IFDIR)
                        or (mode==stat.S_IFDIR and not info.is_dir())
                        or info.external_attr & 0x400
                        or info.flag_bits & ~0x80e
                        or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)):
                    raise ValueError('중복·암호화·링크·특수 파일 또는 지원하지 않는 ZIP 항목입니다.')
                seen[name]=info.is_dir()
                if info.header_offset!=cursor or cursor+30>offset:
                    raise ValueError('ZIP 로컬 목록에 숨겨진 데이터 또는 잘못된 위치가 있습니다.')
                head=struct.unpack_from('<4s5H3I2H',content,cursor)
                if head[0]!=b'PK\x03\x04' or head[2]!=info.flag_bits or head[3]!=info.compress_type:
                    raise ValueError('ZIP 로컬 헤더와 목록이 일치하지 않습니다.')
                start=cursor+30+head[9]+head[10]
                stop=start+info.compress_size
                if stop>offset:
                    raise ValueError('ZIP 데이터 범위가 올바르지 않습니다.')
                local_name=content[cursor+30:cursor+30+head[9]].decode('utf-8' if info.flag_bits&0x800 else 'cp437')
                if local_name!=info.filename:
                    raise ValueError('ZIP 원본 파일 이름과 목록이 다릅니다.')
                if not info.flag_bits&8 and (head[6],head[7],head[8])!=(info.CRC,info.compress_size,info.file_size):
                    raise ValueError('ZIP 원본 크기 또는 CRC와 목록이 다릅니다.')
                allowance=MAX_EXPANDED_BYTES-total
                if info.filename==SETTINGS_PATH: allowance=min(allowance,MAX_SETTINGS_BYTES)
                if info.filename==MODEL_PATH: allowance=min(allowance,MAX_MODEL_XML_BYTES)
                if info.file_size>allowance:
                    raise ValueError('프로젝트 압축 해제 또는 설정/XML 크기 제한을 초과했습니다.')
                compressed=content[start:stop]
                if info.compress_type==zipfile.ZIP_STORED:
                    raw=compressed
                else:
                    decoder=zlib.decompressobj(-zlib.MAX_WBITS)
                    raw=decoder.decompress(compressed,allowance+1)
                    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                        raise ValueError('DEFLATE 크기 제한 초과 또는 숨겨진/잘린 데이터가 있습니다.')
                if len(raw)>allowance or len(raw)!=info.file_size or zlib.crc32(raw)!=info.CRC:
                    raise ValueError('ZIP 실제 데이터 크기 또는 CRC가 일치하지 않습니다.')
                total+=len(raw); cursor=stop
                if info.flag_bits&8:
                    if content[cursor:cursor+4]==b'PK\x07\x08': cursor+=4
                    if cursor+12>offset or struct.unpack_from('<3I',content,cursor)!=(info.CRC,info.compress_size,info.file_size):
                        raise ValueError('ZIP 후행 크기 또는 CRC가 다릅니다.')
                    cursor+=12
                if info.is_dir():
                    if raw: raise ValueError('ZIP 폴더는 비어 있어야 합니다.')
                else: result[info.filename]=raw
            if cursor!=offset:
                raise ValueError('ZIP 목록 앞에 숨겨진 데이터가 있습니다.')
            for path in seen:
                parts=path.split('/')
                if any('/'.join(parts[:i]) in seen and not seen['/'.join(parts[:i])] for i in range(1,len(parts))):
                    raise ValueError('ZIP 파일과 폴더 경로가 충돌합니다.')
            return result
    except (zipfile.BadZipFile,NotImplementedError,UnicodeError,struct.error,zlib.error,OverflowError) as exc:
        raise ValueError('프로젝트 ZIP 구조 또는 CRC가 손상되었습니다.') from exc


def _settings(raw):
    def pairs(values):
        result={}
        for key,value in values:
            if key in result: raise ValueError('중복 JSON 키가 있습니다.')
            result[key]=value
        return result
    def constant(value):
        raise ValueError('JSON에 유한한 값이 필요합니다: '+value)
    try:
        text=raw.decode('utf-8')
        value=json.loads(text,object_pairs_hook=pairs,parse_constant=constant)
        if not isinstance(value,dict): raise ValueError('프로젝트 설정은 JSON 객체여야 합니다.')
        pending=[(value,0)]
        while pending:
            item,depth=pending.pop()
            if depth>MAX_SETTINGS_DEPTH: raise ValueError('프로젝트 설정 JSON 중첩 제한을 초과했습니다.')
            if isinstance(item,dict): pending.extend((v,depth+1) for pair in item.items() for v in pair)
            elif isinstance(item,list): pending.extend((v,depth+1) for v in item)
            elif isinstance(item,float) and not math.isfinite(item): raise ValueError('유한한 JSON 숫자가 필요합니다.')
            elif isinstance(item,str): item.encode('utf-8')
        return value,text
    except (UnicodeError,json.JSONDecodeError,RecursionError) as exc:
        raise ValueError('올바른 UTF-8 프로젝트 설정 JSON이 필요합니다.') from exc


def _xml(raw):
    try:
        text=raw.decode('utf-8')
        if re.search(r'<!\s*(?:DOCTYPE|ENTITY)',text,re.I):
            raise ValueError('XML DTD와 엔티티 선언은 지원하지 않습니다.')
        return ET.fromstring(text)
    except (UnicodeError,ET.ParseError) as exc:
        raise ValueError('올바른 UTF-8 모델 XML이 필요합니다.') from exc


def _metadata(root):
    if root.tag!='{'+CORE+'}model': raise ValueError('지원하는 3MF model XML이 필요합니다.')
    values={}
    for item in root.findall('{'+CORE+'}metadata'):
        key=item.get('name')
        if not key or key in values or len(item): raise ValueError('모델 producer metadata가 없거나 중복/모호합니다.')
        values[key]=item.text or ''
    if not values.get('Application') or not values.get('BambuStudio:3mfVersion'):
        raise ValueError('프로젝트 Application과 BambuStudio:3mfVersion metadata가 필요합니다.')
    return values


def _xml_bytes(root,namespace):
    """Serialize our known namespace without ElementTree's process-global map."""
    root=copy.deepcopy(root)
    for element in root.iter():
        if not element.tag.startswith('{'+namespace+'}'):
            raise ValueError('생성 CAD의 추가 XML namespace는 지원하지 않습니다.')
        element.tag=element.tag[len(namespace)+2:]
        for name in list(element.attrib):
            if name.startswith('{http://www.w3.org/XML/1998/namespace}'):
                element.set('xml:'+name.split('}',1)[1],element.attrib.pop(name))
            elif name.startswith('{'):
                raise ValueError('생성 CAD의 추가 XML attribute namespace는 지원하지 않습니다.')
    root.set('xmlns',namespace)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)


def _assess(settings,producer):
    issues=[]
    def issue(code,message,field=None):
        entry={'code':code,'message':message}
        if field: entry['field']=field
        issues.append(entry)
    if producer['application']!='BambuStudio-'+QUALIFIED_VERSION or producer['format_version']!='1' or settings.get('version')!=QUALIFIED_VERSION:
        issue('unsupported_version','Bambu Studio 02.09.01.70 / 3MF 형식 1 프로젝트만 지원합니다. 원본 버전을 변경하지 마세요.')
    if settings.get('from')!='project' or settings.get('name')!='project_settings' or settings.get('printer_technology')!='FFF':
        issue('unsupported_project','FFF 프로젝트의 병합된 전역 설정이 필요합니다.')
    # The pinned Config.cpp project loader consumes native strings and arrays.
    # Bare numbers/objects are skipped; a mixed-type array can stop the remaining
    # settings from loading. Preserve unsupported originals for inspection, but
    # do not offer a prepared project that silently substitutes native defaults.
    def native_value(value):
        if isinstance(value,str): return True
        if not isinstance(value,list): return False
        return (all(isinstance(item,str) for item in value)
                or all(isinstance(item,list) and all(isinstance(part,str) for part in item) for item in value))
    for key,value in settings.items():
        if not native_value(value):
            issue('invalid_native_representation','Studio 문자열 또는 같은 형식의 문자열 배열 설정이 필요합니다. 원본 값을 자동 변환하지 않습니다.',key)
    for key in ('post_process','post_process_script','post_process_scripts'):
        value=settings.get(key)
        if value and value!=['']: issue('host_program','호스트 후처리 프로그램이 있는 프로젝트는 사용할 수 없습니다.',key)
    for key in ('filament_settings_id',*FILAMENT_FIELDS,'nozzle_diameter'):
        value=settings.get(key)
        if not isinstance(value,list) or len(value)!=1:
            issue('single_material_nozzle_required','한 필라멘트와 한 노즐의 명시적인 설정이 필요합니다.',key)
    # Native 2.9 explicit topology fields must agree on the one active extruder.
    for key in ('printer_extruder_id','print_extruder_id','physical_extruder_map','extruder_nozzle_count'):
        value=settings.get(key)
        expected='0' if key=='physical_extruder_map' else '1'
        if value!=[expected]: issue('single_extruder_required','한 활성 익스트루더 프로젝트만 지원합니다.',key)
    for key in ('printer_settings_id','print_settings_id','printer_model'):
        if not isinstance(settings.get(key),str) or not settings[key].strip(): issue('missing_identity','기록된 프린터/프로세스 이름이 필요합니다.',key)
    plate=settings.get('curr_bed_type'); prefix=PLATE_BED_PREFIXES.get(plate) if isinstance(plate,str) else None
    if not prefix: issue('unsupported_plate','지원하는 명시적 플레이트 선택이 필요합니다.','curr_bed_type')
    bed_fields=(prefix+'_temp',prefix+'_temp_initial_layer') if prefix else ()
    expected={}
    keys=('printer_settings_id','print_settings_id','filament_settings_id',*MACHINE_FIELDS,*PROCESS_FIELDS,*FILAMENT_FIELDS,'curr_bed_type',*bed_fields)
    for key in keys:
        if key not in settings: issue('missing_core_setting','필수 전역 설정이 없습니다.',key)
        else: expected[key]=copy.deepcopy(settings[key])
    numeric=('nozzle_diameter','printable_height',*PROCESS_FIELDS,*FILAMENT_FIELDS[1:],*bed_fields)
    for key in numeric:
        value=settings.get(key)
        vals=value if isinstance(value,list) else [value]
        try:
            if not vals or len(vals)!=1: raise ValueError()
            raw=vals[0]
            if isinstance(raw,bool) or not isinstance(raw,(str,int,float)): raise ValueError()
            n=float(str(raw).removesuffix('%') if key=='sparse_infill_density' else raw)
            zero=key in ('wall_loops','top_shell_layers','bottom_shell_layers','sparse_infill_density')
            if not math.isfinite(n) or n<0 or (not zero and n==0): raise ValueError()
            if key=='sparse_infill_density' and n>100: raise ValueError()
            if key in ('wall_loops','top_shell_layers','bottom_shell_layers') and n!=int(n): raise ValueError()
        except (TypeError,ValueError,OverflowError): issue('invalid_core_setting','유효한 기록 숫자와 양의 선택 베드 온도가 필요합니다.',key)
    for key in ('machine_start_gcode','machine_end_gcode'):
        if not isinstance(settings.get(key),str): issue('invalid_core_setting','네이티브 G-code 문자열이 필요합니다.',key)
    area=settings.get('printable_area')
    try:
        if not isinstance(area,list) or not 3<=len(area)<=128: raise ValueError()
        points=[tuple(float(n) for n in re.split('[x,]',v)) for v in area]
        if any(len(p)!=2 or not all(math.isfinite(n) for n in p) for p in points): raise ValueError()
        if abs(sum(x*points[(i+1)%len(points)][1]-y*points[(i+1)%len(points)][0] for i,(x,y) in enumerate(points)))==0: raise ValueError()
    except (TypeError,ValueError): issue('invalid_core_setting','유효한 출력 영역 경계점이 필요합니다.','printable_area')
    for key in ('filament_type','filament_settings_id'):
        value=settings.get(key)
        if not isinstance(value,list) or len(value)!=1 or not isinstance(value[0],str) or not value[0].strip(): issue('missing_identity','기록된 재료 이름이 필요합니다.',key)
    return issues,expected,bed_fields


def inspect_studio_project(filename: str,content: bytes)->dict:
    if not isinstance(filename,str) or '/' in filename or '\\' in filename or not filename.lower().endswith('.3mf'):
        raise ValueError('원본 .3mf 파일 이름이 필요합니다.')
    _safe_name(filename)
    members=_members(content)
    if SETTINGS_PATH not in members or MODEL_PATH not in members:
        raise ValueError('프로젝트 전역 설정과 루트 모델 XML이 필요합니다.')
    settings,text=_settings(members[SETTINGS_PATH]); metadata=_metadata(_xml(members[MODEL_PATH]))
    producer={'application':metadata['Application'],'format_version':metadata['BambuStudio:3mfVersion'],'settings_version':settings.get('version')}
    issues,expected,beds=_assess(settings,producer)
    def scalar(key):
        value=settings.get(key)
        return copy.deepcopy(value[0] if isinstance(value,list) and len(value)==1 else value)
    mapping={'printer_model':'printer_model','printer_preset':'printer_settings_id','process_preset':'print_settings_id',
             'nozzle_diameter':'nozzle_diameter','plate_type':'curr_bed_type','filament_name':'filament_settings_id',
             'filament_type':'filament_type','nozzle_temperature':'nozzle_temperature',
             'nozzle_temperature_initial_layer':'nozzle_temperature_initial_layer','filament_flow_ratio':'filament_flow_ratio',
             'filament_max_volumetric_speed':'filament_max_volumetric_speed'}
    summary={key:scalar(field) for key,field in mapping.items()}
    summary.update(bed_temperature=scalar(beds[0]) if beds else None,bed_temperature_initial_layer=scalar(beds[1]) if beds else None)
    return {'schema_version':1,'source':{'filename':filename,'bytes':len(content),'sha256':_hash(content)},
            'producer':producer,'settings_text':text,'settings_sha256':_hash(members[SETTINGS_PATH]),
            'summary':summary,'expected_settings':expected,'supported':not issues,'issues':issues,
            'warnings':['파일의 producer 표시는 형식 주장으로, 발행처 인증이나 설치된 프린터의 측정값이 아닙니다.',
                        '전역 설정만 옮깁니다. 원본 모델·객체/플레이트별 설정·페인팅·높이별 코드는 옮기지 않습니다.']}


def public_snapshot(snapshot):
    return copy.deepcopy({key:value for key,value in snapshot.items() if key not in ('settings_text','expected_settings')})


def build_project_3mf(model_bytes: bytes,snapshot: dict)->tuple[bytes,dict]:
    settings_bytes=snapshot['settings_text'].encode('utf-8')
    settings,_=_settings(settings_bytes)
    issues,expected,_=_assess(settings,snapshot['producer'])
    if (issues or not snapshot.get('supported') or _hash(settings_bytes)!=snapshot['settings_sha256']
            or expected!=snapshot['expected_settings']):
        raise ValueError('지원하는 검증된 원본 설정 snapshot이 필요합니다.')
    source_hash=snapshot['source']['sha256']
    if not isinstance(source_hash,str) or not re.fullmatch('[0-9a-f]{64}',source_hash): raise ValueError('원본 해시가 필요합니다.')
    payload=_members(model_bytes)
    if set(payload)!={'[Content_Types].xml','_rels/.rels',MODEL_PATH}:
        raise ValueError('앱이 생성한 최소 3MF 모델만 사용할 수 있습니다.')
    root=_xml(payload[MODEL_PATH]); q=lambda name:'{'+CORE+'}'+name
    relationships=_xml(payload['_rels/.rels'])
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    if (relationships.tag!='{'+relns+'}Relationships' or len(relationships)!=1
            or relationships[0].tag!='{'+relns+'}Relationship'
            or relationships[0].get('Type')!='http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel'
            or relationships[0].get('Target') not in ('/3D/3dmodel.model','3D/3dmodel.model')
            or relationships[0].get('TargetMode') not in (None,'Internal')):
        raise ValueError('생성 CAD의 내부 모델 relationship이 필요합니다.')
    objects=root.findall(q('resources')+'/'+q('object')); items=root.findall(q('build')+'/'+q('item'))
    components=objects[1].findall(q('components')+'/'+q('component')) if len(objects)==2 else []
    if (root.tag!=q('model') or root.get('unit')!='millimeter' or len(objects)!=2 or len(items)!=1 or len(components)!=1
            or objects[0].get('id')!='0' or objects[1].get('id')!='1' or components[0].get('objectid')!='0'
            or items[0].get('objectid')!='1' or items[0].get('transform') or components[0].get('transform')
            or objects[0].find(q('mesh')) is None):
        raise ValueError('하나의 mm 메시와 변환 없는 build instance를 가진 앱 CAD가 필요합니다.')
    if (len(root.findall(q('resources')))!=1 or len(root.findall(q('build')))!=1
            or len(root.find(q('resources')))!=2 or len(root.find(q('build')))!=1
            or [child.tag for child in objects[0]]!=[q('mesh')]
            or [child.tag for child in objects[1]]!=[q('components')]
            or len(objects[1].find(q('components')))!=1
            or any(child.tag not in (q('metadata'),q('resources'),q('build')) for child in root)
            or any(key not in ('id','type','name') for obj in objects for key in obj.attrib)
            or any(key!='objectid' for key in components[0].attrib)
            or any(key not in ('objectid','printable') for key in items[0].attrib)):
        raise ValueError('생성 CAD 외 추가 geometry/extension은 지원하지 않습니다.')
    mesh=objects[0].find(q('mesh')); mesh_before=_xml_bytes(mesh,CORE)
    if [child.tag for child in mesh]!=[q('vertices'),q('triangles')]:
        raise ValueError('생성 CAD 메시 구조가 올바르지 않습니다.')
    vertices=mesh.findall(q('vertices')+'/'+q('vertex')); triangles=mesh.findall(q('triangles')+'/'+q('triangle'))
    try:
        coords=[tuple(float(v.attrib[k]) for k in ('x','y','z')) for v in vertices]
        indices=[tuple(int(t.attrib[k]) for k in ('v1','v2','v3')) for t in triangles]
        if not coords or not indices or any(not all(math.isfinite(n) for n in p) for p in coords) or any(n<0 or n>=len(coords) for t in indices for n in t): raise ValueError()
    except (KeyError,TypeError,ValueError,OverflowError) as exc: raise ValueError('유효한 생성 CAD 메시가 필요합니다.') from exc
    objects[0].set('id','1'); objects[1].set('id','2'); components[0].set('objectid','1'); items[0].set('objectid','2')
    metadata={'Application':snapshot['producer']['application'],'BambuStudio:3mfVersion':'1',
              '3DPrinterAgent:ModifiedBy':MODIFIER,'3DPrinterAgent:SourceProjectSHA256':source_hash,
              '3DPrinterAgent:ModelSHA256':_hash(model_bytes)}
    for item in list(root.findall(q('metadata'))):
        if item.get('name') in metadata: root.remove(item)
    for name,value in reversed(list(metadata.items())):
        item=ET.Element(q('metadata'),{'name':name}); item.text=value; root.insert(0,item)
    if _xml_bytes(mesh,CORE)!=mesh_before: raise ValueError('CAD geometry가 변경되었습니다.')
    payload[MODEL_PATH]=_xml_bytes(root,CORE)
    payload[SETTINGS_PATH]=settings_bytes
    payload['Metadata/model_settings.config']=b'''<?xml version="1.0" encoding="UTF-8"?>
<config><object id="2"><metadata key="name" value="generated-model"/><metadata key="extruder" value="1"/><part id="1" subtype="normal_part"><metadata key="name" value="generated-model"/></part></object><plate><metadata key="plater_id" value="1"/><metadata key="plater_name" value="Generated CAD"/><metadata key="locked" value="false"/><model_instance><metadata key="object_id" value="2"/><metadata key="instance_id" value="0"/><metadata key="identify_id" value="1"/></model_instance></plate><assemble/></config>'''
    types=_xml(payload['[Content_Types].xml'])
    typesns='http://schemas.openxmlformats.org/package/2006/content-types'
    if types.tag!='{'+typesns+'}Types' or any(child.tag not in ('{'+typesns+'}Default','{'+typesns+'}Override') for child in types):
        raise ValueError('생성 CAD content types 구조가 올바르지 않습니다.')
    for name in (SETTINGS_PATH,'Metadata/model_settings.config'):
        ET.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Override',{'PartName':'/'+name,'ContentType':'text/plain'})
    payload['[Content_Types].xml']=_xml_bytes(types,typesns)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(payload):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG|0o600)<<16; archive.writestr(info,payload[name])
    content=stream.getvalue()
    geometry={'preserved':True,'vertices':len(vertices),'triangles':len(triangles),
              'dimensions_mm':[max(p[i] for p in coords)-min(p[i] for p in coords) for i in range(3)],
              'mesh_sha256':_hash(mesh_before),'source_geometry_copied':False}
    return content,{'schema_version':1,'source_sha256':source_hash,'settings_sha256':snapshot['settings_sha256'],
                    'model_sha256':_hash(model_bytes),'project_sha256':_hash(content),'project_bytes':len(content),
                    'producer':copy.deepcopy(snapshot['producer']),'modifier':MODIFIER,'geometry':geometry,
                    'settings_preserved':True,'application_policy':'preserve supplied source-template marker; explicit modifier identifies derivative',
                    'application_origin':'source project root Application metadata; not newly asserted Studio authorship',
                    'qualification_version':QUALIFIED_VERSION}
