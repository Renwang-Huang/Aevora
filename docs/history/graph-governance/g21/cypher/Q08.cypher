MATCH(s:TenantState {id:$state}),(session:Session {id:$session}) RETURN properties(s),properties(session) LIMIT 2
