# Pilot Incident Response

## Severity Levels

| Level | Description | Response Time | Action |
|-------|-------------|---------------|--------|
| P0 | Security leak, data exposure, system down | Immediate | Stop pilot, rollback, incident report |
| P1 | Compliance violation, crisis mishandled | < 1 hour | Fix, review all affected sessions |
| P2 | Tone quality degradation, wrong info | Same day | KB fix, retest |
| P3 | Minor UX issue, KB gap | Next review | Track, fix in next iteration |

## Incident Types and Response

### P0: Security / Data Leak

**Symptoms:**
- Admin/internal content visible to parent/student
- Source lines shown to non-privileged roles
- SQL injection, SSRF bypass, or RLS bypass
- Unauthorized access to other users' sessions

**Immediate Action:**
1. Stop pilot immediately
2. Revoke all non-admin access tokens
3. Restore from backup if data corrupted
4. Escalate to technical lead
5. Document incident with timestamp, affected users, exposed data
6. Fix root cause before restarting pilot

### P0: System Down

**Symptoms:**
- API not responding
- Database unreachable
- Health checks failing

**Immediate Action:**
1. Check `docker ps` and container logs
2. Check PostgreSQL connectivity
3. Run `make check-runtime`
4. Restart if safe: `docker-compose restart`
5. If recovery needed: `make restore BACKUP_FILE=<latest>`

### P1: Compliance Violation

**Symptoms:**
- AI made a promise (guarantee, commitment)
- AI exposed pricing/sales scripts to parent
- AI provided clinical/medical advice

**Action:**
1. Review the conversation immediately
2. If the message was sent to a real parent: contact the parent with a correction
3. Fix the compliance rule if needed
4. Add the violating phrase to the blocklist
5. Review all sessions from the same day for similar issues

### P1: Crisis Mishandling

**Symptoms:**
- Crisis message not escalated
- Non-crisis message escalated incorrectly
- Inappropriate response to crisis (e.g., suggested enrollment)

**Action:**
1. Review the crisis detection for that message
2. Verify handoff was triggered
3. If real crisis was missed: immediate human follow-up
4. Update crisis detection keywords if needed
5. Review all crisis-adjacent messages

### P2: Wrong Information

**Symptoms:**
- Incorrect fee quoted
- Wrong campus information
- Outdated policy referenced
- Expired document still in index

**Action:**
1. Identify the source document
2. Update or deprecate the document
3. Re-index: `make sync-db-index`
4. Note in daily review

### P2: Tone Quality Degradation

**Symptoms:**
- Mechanical phrases appearing
- Source lines leaking
- Answers feel more robotic than before
- Emotional support answers feel cold

**Action:**
1. Compare with previous day's samples
2. Check if any recent code changes affected tone
3. Review the mechanical phrase sanitizer
4. Add new banned phrases if needed
5. Re-run: `make benchmark-tone-quality`

## Rollback Procedure

If pilot quality is unacceptable:

1. **Stop new sessions**: Set maintenance mode or rate-limit to 0
2. **Complete active sessions**: Wait for in-progress chats to finish
3. **Backup**: `make backup`
4. **Document**: What went wrong, which metrics failed
5. **Fix**: Address the root cause
6. **Re-validate**: `make release-check`
7. **Restart**: With limited scope (fewer counselors, fewer features)

## Communication Template

### Internal Incident Report

```
Incident ID: P4.5-INC-XXX
Date/Time:
Severity: P0 / P1 / P2 / P3

What happened:

Who/What was affected:

Root cause:

Immediate action taken:

Long-term fix:

Lessons learned:

Reported by:
Reviewed by:
```

## Emergency Contacts

| Role | Name | Phone | WeChat |
|------|------|-------|--------|
| Technical Lead | | | |
| Product Lead | | | |
| Admissions Director | | | |
| Counselor Lead | | | |

*(Fill in before pilot start)*
