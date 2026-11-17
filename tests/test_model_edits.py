"""Pure contextual-edit regressions; no CAD, provider or filesystem required."""
import copy
import hashlib
import importlib
import importlib.util
import json
import subprocess
import unittest

BASE = {'template':'tray','width':150,'depth':90,'height':30,'wall':2,'bottom':2,'dividers':2}


def javascript_json_roundtrip(value):
    """Use the actual JSON serialization boundary exercised by browser clients."""
    result = subprocess.run(
        ['node', '-e', "process.stdout.write(JSON.stringify(JSON.parse(require('fs').readFileSync(0, 'utf8'))))"],
        input=json.dumps(value, ensure_ascii=False, allow_nan=False),
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


class ModelEditTests(unittest.TestCase):
    def engine(self):
        self.assertIsNotNone(importlib.util.find_spec('print_agent.model_edits'), 'contextual edit engine is missing')
        return importlib.import_module('print_agent.model_edits')

    def selection(self, operations=None, **overrides):
        return {'schema_version':1,'request_text':'높이를 5mm 늘려줘','base_parameters':dict(BASE),
                'operations':operations or [{'field':'height','op':'add','value':5}], 'parent':None, **overrides}

    def test_actual_javascript_roundtrip_preserves_operation_and_record_hashes(self):
        engine=self.engine()
        for value in (5, 5.0, 0.2, -0.2, 0, 0.0, -0.0):
            with self.subTest(value=repr(value)):
                review=engine.review_model_edit(self.selection([
                    {'field':'height','op':'add','value':value},
                    {'field':'wall','op':'set','value':1.8},
                    {'field':'dividers','op':'set','value':3}]))
                wire=javascript_json_roundtrip(review)
                record=engine.model_edit_record(wire['selection'],wire['parameters'])
                self.assertEqual(record['review_sha256'],review['review_sha256'])
                self.assertEqual(record['base_sha256'],review['base_sha256'])
                self.assertEqual(record['parameters_sha256'],review['parameters_sha256'])
                self.assertEqual(engine.validate_model_edit_record(record,wire['parameters']),record)
                self.assertIs(type(record['selection']['operations'][2]['value']),int)

    def test_signed_zero_base_has_one_canonical_representation(self):
        engine=self.engine()
        cable={'template':'cable_comb','width':80,'depth':18,'height':12,'wall':2,'bottom':2,
               'slots':5,'cable_diameter':6,'fit_clearance':-0.0}
        negative=engine.normalize_parameters(cable)
        positive=engine.normalize_parameters({**cable,'fit_clearance':0.0})
        self.assertEqual(json.dumps(negative,sort_keys=True),json.dumps(positive,sort_keys=True))

    def test_actual_javascript_roundtrip_keeps_signed_zero_parent_binding(self):
        engine=self.engine()
        cable={'template':'cable_comb','width':80,'depth':18,'height':12,'wall':2,'bottom':2,
               'slots':5,'cable_diameter':6,'fit_clearance':-0.0}
        normalized=engine.normalize_parameters(cable)
        base_hash=hashlib.sha256(json.dumps(normalized,ensure_ascii=False,sort_keys=True,
                                          separators=(',',':'),allow_nan=False).encode()).hexdigest()
        parent={'job_id':'a'*32,'parameters_sha256':base_hash,'model_sha256':'b'*64,'manifest_sha256':'c'*64}
        review=engine.review_model_edit(self.selection([
            {'field':'height','op':'set','value':13.0},
            {'field':'fit_clearance','op':'add','value':-0.0}],base_parameters=cable,parent=parent))
        wire=javascript_json_roundtrip(review)
        record=engine.model_edit_record(wire['selection'],wire['parameters'])
        self.assertEqual(record['review_sha256'],review['review_sha256'])
        self.assertEqual(record['selection']['parent'],parent)
        self.assertEqual(record['base_sha256'],base_hash)

    def test_relative_edit_preserves_every_unspecified_field(self):
        engine=self.engine()
        review=engine.review_model_edit(self.selection())
        self.assertEqual(review['parameters']['height'],35)
        self.assertEqual(review['changes'],[{'field':'height','before':30,'after':35}])
        self.assertEqual({k:v for k,v in review['parameters'].items() if k!='height'},
                         {k:v for k,v in review['selection']['base_parameters'].items() if k!='height'})
        self.assertEqual(len(review['parameters']),12)

    def test_decimal_addition_does_not_leave_binary_roundoff(self):
        engine=self.engine()
        review=engine.review_model_edit(self.selection([{'field':'wall','op':'add','value':-0.2}]))
        self.assertEqual(review['parameters']['wall'],1.8)

    def test_normalization_requires_complete_strict_applicable_values(self):
        engine=self.engine()
        invalid=[{}, {**BASE,'width':True}, {**BASE,'width':'150'}, {**BASE,'height':float('nan')},
                 {**BASE,'dividers':2.0}, {**BASE,'slots':6}, {**BASE,'code':'x'},
                 {k:v for k,v in BASE.items() if k!='wall'}]
        for base in invalid:
            with self.subTest(base=base), self.assertRaises(ValueError):
                engine.normalize_parameters(base)
        self.assertEqual(engine.normalize_parameters(BASE)['slots'],5)

    def test_operations_are_strict_and_never_partial(self):
        engine=self.engine()
        invalid=[[], [{'field':'height','op':'set','value':30}],
                 [{'field':'height','op':'add','value':5}]*2,
                 [{'field':'height','op':'multiply','value':2}],
                 [{'field':'height','op':'set','value':True}],
                 [{'field':'height','op':'set','value':'35'}],
                 [{'field':'height','op':'set','value':float('inf')}],
                 [{'field':'height','op':'set','value':35,'code':'x'}],
                 [{'field':'slots','op':'set','value':6}],
                 [{'field':'dividers','op':'add','value':1}],
                 [{'field':'dividers','op':'set','value':3.0}],
                 [{'field':'height','op':'set','value':2}]]
        for operations in invalid:
            with self.subTest(operations=operations), self.assertRaises(ValueError):
                engine.review_model_edit(self.selection(operations=operations) | {'operations':operations})

    def test_cross_field_constraints_cover_all_templates(self):
        engine=self.engine()
        bases=[{**BASE,'width':10,'wall':5},
               {'template':'cable_comb','width':30,'depth':18,'height':12,'wall':2,'bottom':2,'slots':5,'cable_diameter':6,'fit_clearance':0.3},
               {'template':'magnet_frame','width':65,'depth':65,'height':7,'wall':2,'bottom':2,'inset_diameter':52,'inset_depth':6,'fit_clearance':0.3}]
        for base in bases:
            with self.subTest(template=base['template']), self.assertRaises(ValueError):
                engine.normalize_parameters(base)

    def test_selection_rejects_unknown_keys_bad_version_request_and_parent(self):
        engine=self.engine()
        for change in ({'schema_version':True},{'schema_version':1.0},{'request_text':' '},
                       {'request_text':'x'*4001},{'extra':1},{'parent':{}},
                       {'parent':{'job_id':'a'*32,'parameters_sha256':'0'*64,'model_sha256':'b'*64,'manifest_sha256':'c'*64}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                engine.review_model_edit(self.selection(**change))

    def test_canonical_hashes_and_record_rederivation_reject_tampering(self):
        engine=self.engine()
        selection=self.selection(request_text='  높이를 5mm 늘려줘\n')
        review=engine.review_model_edit(selection)
        canonical=lambda value: json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        self.assertEqual(review['base_sha256'],hashlib.sha256(canonical(review['selection']['base_parameters'])).hexdigest())
        hashed={key:review[key] for key in ('schema_version','selection','base_sha256','parameters_sha256','changes')}
        self.assertEqual(review['review_sha256'],hashlib.sha256(canonical(hashed)).hexdigest())
        self.assertEqual(review['selection']['request_text'],selection['request_text'])
        record=engine.model_edit_record(selection,review['parameters'])
        self.assertEqual(record['provenance'],'user_confirmed_parameters')
        self.assertEqual(engine.validate_model_edit_record(record,review['parameters']),record)
        for key in ('review_sha256','changes','parameters','provenance','extra'):
            changed=copy.deepcopy(record)
            changed[key]='tampered'
            with self.subTest(key=key), self.assertRaises(ValueError):
                engine.validate_model_edit_record(changed,review['parameters'])
        with self.assertRaises(ValueError):
            engine.model_edit_record(selection,{**review['parameters'],'width':160})

    def test_parent_hash_is_bound_to_normalized_base(self):
        engine=self.engine()
        review=engine.review_model_edit(self.selection())
        parent={'job_id':'a'*32,'parameters_sha256':review['base_sha256'],'model_sha256':'b'*64,'manifest_sha256':'c'*64}
        self.assertEqual(engine.review_model_edit(self.selection(parent=parent))['selection']['parent'],parent)
        with self.assertRaises(ValueError):
            engine.review_model_edit(self.selection(parent={**parent,'job_id':'A'*32}))

    def test_rules_absolute_relative_units_counts_and_qualified_fields(self):
        engine=self.engine()
        for text, changes in [('높이를 5mm 늘려줘',{'height':35}),('높이만 5mm 늘려줘',{'height':35}),('높이를 0.5cm 줄여줘',{'height':25}),
                              ('가로 160mm, 4칸',{'width':160,'dividers':3}),('벽 두께를 0.2mm 줄여줘',{'wall':1.8}),
                              ('바닥 두께 0.3cm로 바꿔줘',{'bottom':3})]:
            with self.subTest(text=text):
                result=engine.plan_model_edit(text,BASE)
                self.assertEqual(result['status'],'ready')
                self.assertEqual(result['capability'],'current_template_parameters_only')
                self.assertEqual({c['field']:c['after'] for c in result['review']['changes']},changes)
                self.assertEqual(result['questions'],[])
                self.assertEqual(result['assumptions'],[])

    def test_applicable_template_count_aliases_accept_explicit_integer_counts(self):
        engine=self.engine()
        cable={'template':'cable_comb','width':80,'depth':18,'height':12,'wall':2,'bottom':2,'slots':5,'cable_diameter':6,'fit_clearance':0.3}
        for text,base,field,after in [('칸막이 3개',BASE,'dividers',3),('슬롯 6개',cable,'slots',6),
                                      ('케이블 지름을 0.1cm 늘려줘',cable,'cable_diameter',7)]:
            with self.subTest(text=text):
                result=engine.plan_model_edit(text,base)
                self.assertEqual(result['status'],'ready')
                self.assertEqual(result['review']['changes'],[{'field':field,'before':base[field],'after':after}])

    def test_ambiguous_mixed_unsupported_conflicting_and_zero_effect_requests_fail_closed(self):
        engine=self.engine()
        for text in ('조금 크게','전체를 2배','케이블 받침으로 바꿔줘','높이 35mm 그리고 손잡이 추가',
                     '높이 35mm, 무늬는 줄무늬','색은 청록','높이 35mm, 높이 40mm','높이 30mm','케이블 지름 7mm',
                     '가로 160mm 5mm','가로 160mm 또는 높이 35mm','가로 160인치','가로 160mm 알 수 없는 작업'):
            with self.subTest(text=text):
                result=engine.plan_model_edit(text,BASE)
                self.assertEqual(result['status'],'needs_input')
                self.assertNotIn('review',result)
                self.assertNotIn('parameters',result)
