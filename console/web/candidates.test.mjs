import test from 'node:test';
import assert from 'node:assert/strict';
import {candidatePresentation} from './candidates.js';

test('candidate explains missing bounds from Core without promoting declarations',()=>{
 const view=candidatePresentation({title:'升级观察',public_summary:'恢复前核对备份'},
  {next_action:'DECLARE_BOUNDS',missing_fields:['necessary_conditions','scope'],unknown_required_facts:[]});
 assert.equal(view.title,'升级观察');assert.deepEqual(view.missing,['必要条件','适用范围']);
 assert.match(view.explanation,/新的有界候选/);
});
test('missing checklist remains unknown and a source check does not imply publication',()=>{
 const absent=candidatePresentation({},undefined);assert.equal(absent.missing,null);assert.equal(absent.unknown,null);
 const reviewed=candidatePresentation({title:'观察'},{next_action:'REVIEW_ADMISSION',missing_fields:[],unknown_required_facts:[]});
 assert.match(reviewed.explanation,/显式审核/);assert.doesNotMatch(reviewed.explanation,/已发布/);
});
