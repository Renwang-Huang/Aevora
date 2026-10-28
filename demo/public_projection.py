"""Explicit PUBLIC projection shared by Hero replay and the thin Console.

This is a disclosure policy, not a second WHEN/WHY implementation. Nested raw
MCP inputs, private verification receipts and arbitrary graph properties are
never copied. Unknown labels expose only their actual identity.
"""
FIELDS = {
 'Agent': 'id runtime source_type',
 'Task': 'id public_title scenario_version',
 'Context': 'id facts source_type',
 'Experience': 'id title public_summary strategy source_type limitations origin_run_id origin_patch_sha256 publication_candidate_id created_at',
 'ExperienceRevision': 'id experience_id revision_kind revision_reason base_revision_ids created_at declared_rule_id scope',
 'Rule': 'id experience_id version principle strategy created_at valid_from valid_until',
 'Premise': 'id fact_key allowed_values required',
 'Evidence': 'id source_type source_run_id public_summary attribution created_at',
 'VerifiedOutcome': 'id run_id verdict test_count source_type submission_digest evaluator_fingerprint test_suite_fingerprint attribution',
 'Query': 'id run_id created_at query_snapshot_ids decision_engine_version',
 'QuerySnapshot': 'id content_sha256 created_at',
 'Decision': 'id run_id query_id experience_id decision reason verification_steps authority adoption attribution created_at query_snapshot_id',
 'ObservedAction': 'id run_id submission_digest patch_sha256 source_type authority attribution mental_influence strategy_association created_at',
 'Feedback': 'id experience_id outcome_id attribution feedback_status source_type',
 'GovernanceEvent': 'id target_id target_label event_type authority source_type public_reason scope effective_at created_at',
 'AuditEvent': 'id event_type candidate_id record_id authority public_reason created_at',
 'Schema': 'id version',
 'Candidate': 'id run_id body_sha256 authority provenance created_at schema_version title public_summary strategy necessary_conditions inapplicable_conditions scope unknown_fields limitations derived_from_candidate_id',
 'LifecycleHead': 'id candidate_id state sequence event_id',
 'CandidateEvent': 'id candidate_id from_state to_state sequence previous_event_id event_key authority principal reason created_at',
 'SourceVerification': 'id candidate_id run_id origin authority source_sha256 submission_sha256 outcome_id facts native_thread_id source_epoch causal_benefit',
 'ExternalObservation': 'id run_id status authority source_sha256 public_summary created_at trusted_outcome attribution record_kind candidate_id purpose disposition elapsed_seconds',
}
FACTS = frozenset('concurrency_scope worker_count worker_count_known shared_state_kind synchronization_scope transaction_guarantees observed_failure_mode sqlite_journal_mode failure_domain supported_operation_set operation_kind durability_requirement'.split())
FACTS = FACTS | frozenset('shared_object_scope operation_semantics authority_model clock_domain contract_version lease_expiry_semantics authority_validation runtime_os runtime_arch runtime_engine storage_backend console_access'.split())
FACTS = FACTS | {'runtime_version','runtime_revision'}


def project(label, payload):
    if label == 'Candidate' and isinstance(payload.get('body'), dict):
        # Only explicitly public, already validated proposal fields. Never
        # disclose the raw body, source references, receipts or arbitrary keys.
        body = payload['body']
        payload = {**payload, **{k: body[k] for k in (
            'title', 'public_summary', 'strategy', 'necessary_conditions',
            'inapplicable_conditions', 'scope', 'unknown_fields', 'limitations',
            'derived_from_candidate_id') if k in body}}
    result={k:payload[k] for k in FIELDS.get(label,'id').split() if k in payload}
    if 'facts' in result:result['facts']={k:v for k,v in result['facts'].items() if k in FACTS and not isinstance(v,(dict,list))}
    if 'scope' in result:result['scope']={k:v for k,v in result['scope'].items() if k in FACTS}
    return result


def decision_view(row,query_id=None,snapshot_id=None):
    keys='experience_id decision reason rule_ids unknown_premises conflicting_premises missing_premises missing_material_premises matched_premises verification_steps retrieval_snapshot_sha256 current_operation_coverage attribution decision_engine_version'.split()
    result={k:row[k] for k in keys if k in row}
    result.update(query_id=query_id,query_snapshot_id=snapshot_id,decision_id=None,
        support_paths=[{k:p[k] for k in ('path','edge_types')} for p in row.get('principle_support_paths',[])],
        counterexample_paths=[{k:p[k] for k in ('path','edge_types')} for p in row.get('relevant_counterexample_paths',[])])
    return result
