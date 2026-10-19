MATCH(n:V2Record {id:$id}) RETURN labels(n),properties(n) LIMIT 2
