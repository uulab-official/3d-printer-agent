"""Synthetic containers around retained synthetic CI settings; no GUI-export claim."""
import io
import json
from pathlib import Path
import zipfile
from xml.sax.saxutils import escape

VERSION = '02.09.01.70'
CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'


def project_bytes(settings=None, *, settings_overrides=None, application=None,
                  format_version='1', settings_text=None, root_xml=None, extra_members=None):
    if settings is None:
        settings = json.loads((Path(__file__).parent / 'fixtures/studio_project_synthetic_settings.json').read_text())
    settings = dict(settings)
    settings.update(settings_overrides or {})
    if settings_text is None:
        settings_text = json.dumps(settings, ensure_ascii=False, indent=2)
    if isinstance(settings_text, str):
        settings_text = settings_text.encode('utf-8')
    if root_xml is None:
        application = application if application is not None else 'BambuStudio-' + VERSION
        root_xml = (f'<model xmlns="{CORE}" unit="millimeter"><metadata name="Application">{escape(application)}</metadata>'
                    f'<metadata name="BambuStudio:3mfVersion">{escape(format_version)}</metadata>'
                    '<resources/><build/></model>').encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('Metadata/project_settings.config', settings_text)
        archive.writestr('3D/3dmodel.model', root_xml)
        for name, content in (extra_members or {}).items():
            archive.writestr(name, content)
    return stream.getvalue()
