import test from 'node:test';
import assert from 'node:assert/strict';
import {projectGuide,queryResult} from './guidance.js';

test('zero results explain successful activity without inventing experience',()=>{
  const guide=projectGuide({state:'ACTIVITY_RECORDED',counts:{queries:3,available_experiences:0,pending_candidates:0}});
  assert.match(guide.title,/尚无可复用经验/);
  assert.equal(guide.action,'query');
  const result=queryResult({query_snapshot_ids:{}});
  assert.equal(result.count,0);
  assert.match(result.title,/未返回经验/);
});

test('incomplete project aggregates never become a confirmed empty library',()=>{
  for(const value of [null,undefined]){
    const guide=projectGuide({state:'ACTIVITY_RECORDED',counts:{available_experiences:value,pending_candidates:0}});
    assert.doesNotMatch(guide.title,/尚无可复用经验/);
    assert.match(guide.text,/尚需核对/);
  }
  for(const query of [{},{query_snapshot_ids:null},{query_snapshot_ids:[]}]){
    assert.equal(queryResult(query).count,null);
    assert.doesNotMatch(queryResult(query).title,/未返回经验/);
  }
});

test('published and pending states lead to the correct next step',()=>{
  assert.equal(projectGuide({state:'CANDIDATES_PENDING'}).action,'governance');
  const guide=projectGuide({state:'EXPERIENCE_AVAILABLE'});
  assert.equal(guide.action,'explorer');
  assert.match(guide.text,/仍需查询适用性/);
  assert.equal(projectGuide({state:'EMPTY'}).action,'query');
});

test('query explanation counts actual snapshots and keeps historical meaning',()=>{
  const result=queryResult({query_snapshot_ids:{'experience:one':'snapshot:one','experience:two':'snapshot:two'}});
  assert.equal(result.count,2);
  assert.match(result.text,/查询当时的快照/);
  assert.match(result.text,/重新查询/);
});
