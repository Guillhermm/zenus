

# Multi-Agent Collaboration & Proactive Monitoring

Two powerful new features that take Zenus to the next level:

## 🤖 Multi-Agent Collaboration

### What It Does
Deploys specialized AI agents that work together to solve complex tasks:
- **Researcher Agent**: Gathers information and finds potential solutions
- **Planner Agent**: Creates detailed, step-by-step execution plans
- **Executor Agent**: Implements the plan using Zenus tools
- **Validator Agent**: Verifies results and ensures quality

### Why It's Revolutionary
- **Cursor/OpenClaw**: Single AI, single perspective
- **Zenus**: Multiple specialized agents collaborating like a team

### How It Works

**Phase 1: Research**
- Analyzes the problem thoroughly
- Explores 3-5 different approaches
- Identifies tools, challenges, and best practices
- Confidence scoring on findings

**Phase 2: Planning**
- Creates detailed execution plan
- Orders steps with dependencies
- Assesses risks per step
- Includes rollback strategies
- Defines validation checkpoints

**Phase 3: Execution** (if enabled)
- Implements the plan step-by-step
- Handles failures gracefully
- Stops on high-risk failures
- Tracks success/failure per step

**Phase 4: Validation**
- Verifies all steps completed
- Checks results match expectations
- Identifies any issues or warnings
- Makes recommendations for improvement

### Example Output

```bash
zenus --multi-agent "build a REST API for managing todos"
```

```
🤖 Multi-Agent Collaboration: Deploying specialized agents...

Collaboration Summary:
Session ID: a3f7b12e
Agents Involved: researcher, planner, executor, validator
Duration: 45.3s

✓ Researcher Agent
  Confidence: 85%
  Reasoning: Found 5 viable approaches, recommended FastAPI
  Duration: 12.1s

✓ Planner Agent
  Confidence: 90%
  Reasoning: Created 12-step plan with low risk profile
  Duration: 8.7s

✓ Executor Agent
  Confidence: 100%
  Reasoning: Executed 12 steps, 12 succeeded
  Duration: 18.2s

✓ Validator Agent
  Confidence: 95%
  Reasoning: All endpoints working, tests passing, docs generated
  Duration: 6.3s

✓ Collaboration successful!
REST API built successfully with todos CRUD, validation, and OpenAPI docs
```

### Agent Communication

Agents communicate via structured messages:
```python
{
  "from_agent": "researcher",
  "to_agent": "planner",
  "message_type": "response",
  "content": {
    "recommended_approach": "FastAPI + SQLAlchemy",
    "reasoning": "Best balance of speed and features"
  }
}
```

### Usage

**Enable in code:**
```python
from zenus_core.cli.orchestrator import Orchestrator

orch = Orchestrator(enable_multi_agent=True)

# Use multi-agent for complex tasks
result = orch.execute_with_multi_agent("deploy microservices architecture")
```

**Check collaboration results:**
```python
# Session includes all agent results and messages
session = multi_agent.collaborate("task")

print(f"Agents involved: {session.agents_involved}")
print(f"Success: {session.success}")
print(f"Messages exchanged: {len(session.messages)}")

for result in session.results:
    print(f"{result.agent}: {result.reasoning}")
```

### When To Use

**Perfect for:**
- Large, complex projects ("build a web app")
- Research-heavy tasks ("find best database for use case X")
- Multi-step workflows ("setup CI/CD pipeline")
- Tasks requiring validation ("migrate production database")

**Not needed for:**
- Simple commands ("list files")
- Single-tool operations ("git commit")
- Quick queries ("what's my IP?")

---

## 🔍 Proactive Monitoring

### What It Does
Continuously monitors your system and **fixes problems before you notice them**:
- Disk space low? → Cleans old logs automatically
- Service crashed? → Restarts it immediately
- Memory leaking? → Identifies and kills the process
- SSL expiring? → Renews certificate ahead of time

### Why It's Revolutionary
- **Traditional Monitoring**: Alerts you when something breaks
- **Zenus**: Fixes it before it breaks

### Health Checks

**Built-in checks:**
1. **Disk Space**: Warns at 80%, critical at 90%
   - Auto-remediation: Deletes old /tmp files and logs
2. **Memory Usage**: Warns at 80%, critical at 90%
   - Alert only (no auto-kill to prevent data loss)
3. **Log Files**: Warns at 100MB, critical at 500MB
   - Auto-remediation: Rotates or deletes old logs
4. **Service Status**: Checks if services are running
   - Auto-remediation: Restarts crashed services
5. **SSL Certificates**: Warns 30 days before expiry
   - Auto-remediation: Triggers renewal process

### Example Output

```bash
zenus --health-check
```

**All Healthy:**
```
✓ All health checks passed
```

**With Issues:**
```
🔍 Proactive Monitor: Found 2 issue(s)

WARNING: Disk usage at 85% (warning threshold: 80%)
  ✓ Auto-remediated: Deleted 2.3GB of old logs from /tmp

CRITICAL: Memory usage at 91% (critical threshold: 90%)
  ✗ Remediation failed: Manual intervention required
```

### Custom Health Checks

Add your own checks:
```python
from zenus_core.monitoring import HealthCheck

# Check if specific service is running
service_check = HealthCheck(
    name="nginx_status",
    check_type="service",
    threshold={"service_name": "nginx"},
    check_interval=300,  # Check every 5 minutes
    auto_remediate=True,
    remediation_action="systemctl restart nginx"
)

monitor.add_health_check(service_check)
```

**Check types available:**
- `disk`: Disk space monitoring
- `memory`: RAM usage monitoring
- `cpu`: CPU usage (coming soon)
- `service`: Systemd service status
- `log`: Log file size monitoring
- `certificate`: SSL certificate expiry

### Alert Levels

**INFO**: Informational only
- No action needed
- Just good to know

**WARNING**: Attention needed soon
- Auto-remediation attempted if configured
- Manual intervention if auto-fix fails

**CRITICAL**: Immediate attention required
- Auto-remediation attempted immediately
- Escalates if remediation fails

### Auto-Remediation

**Safety First:**
- Only remediates when explicitly configured
- Logs all remediation attempts
- Tracks success/failure rates
- Can be disabled per-check

**Example Remediation Actions:**
```python
# Disk space
remediation_action="find /tmp -type f -mtime +7 -delete"

# Service restart
remediation_action="systemctl restart nginx"

# Log rotation
remediation_action="logrotate /etc/logrotate.d/myapp"

# Memory cleanup
remediation_action="sync && echo 3 > /proc/sys/vm/drop_caches"
```

### Monitoring Sessions

Track monitoring activity over time:
```python
# Start monitoring
session = monitor.start_monitoring(interval=300)  # Check every 5 min

# Get status
status = monitor.get_status()
print(f"Checks run: {status['session']['checks_run']}")
print(f"Alerts generated: {status['session']['alerts_generated']}")
print(f"Auto-remediations: {status['session']['auto_remediations']}")
```

### Storage

Monitoring data stored in `~/.zenus/monitoring/`:
- `health_checks.json`: Configured health checks
- `alerts.json`: Alert history (last 7 days)

### Integration with Orchestrator

```python
orch = Orchestrator(enable_proactive_monitoring=True)

# Monitoring runs automatically in background
# Check status anytime
status = orch.run_health_check()
```

---

## 🎯 Combining Both Features

Multi-Agent + Proactive Monitoring = **Autonomous System Management**

**Scenario**: Deploy new service
1. **Multi-Agent** researches best deployment strategy, plans steps, executes deployment
2. **Proactive Monitor** watches the new service, ensures it stays healthy
3. If service crashes → Monitor restarts it automatically
4. If deployment has issues → Multi-Agent can re-plan and fix

**Example:**
```python
orch = Orchestrator(
    enable_multi_agent=True,
    enable_proactive_monitoring=True
)

# Deploy with multi-agent
result = orch.execute_with_multi_agent("deploy my web app")

# Add health check for the new service
service_check = HealthCheck(
    name="webapp_status",
    check_type="service",
    threshold={"service_name": "my-webapp"},
    check_interval=60,
    auto_remediate=True,
    remediation_action="systemctl restart my-webapp"
)

orch.proactive_monitor.add_health_check(service_check)

# Now your app is deployed AND monitored!
```

---

## 📊 Performance Impact

### Multi-Agent Collaboration
- **Token Usage**: ~2000-5000 tokens per task (4 agents × 500-1250 tokens each)
- **Time**: 20-60 seconds for full collaboration
- **Cost**: ~$0.08-$0.20 per complex task (Anthropic Sonnet 4.5)

**Worth it for:**
- Complex projects (saves hours of manual work)
- High-stakes tasks (validation prevents mistakes)
- Research-heavy work (finds better solutions)

**Skip for:**
- Simple commands (use regular execution)
- Time-sensitive operations (multi-agent is thorough but slower)

### Proactive Monitoring
- **CPU Usage**: <1% (checks run every 5-30 minutes)
- **Memory**: ~10MB (for monitoring daemon)
- **Disk**: ~1MB for logs and history
- **Token Usage**: 0 (no LLM calls, pure system commands)
- **Cost**: $0.00

**Always worth it:** Zero cost, prevents disasters, saves time.

---

## 🧪 Testing

Run tests:
```bash
cd zenus
poetry run pytest packages/core/tests/test_multi_agent_and_monitoring.py -v
```

### Test Coverage
- ✅ Multi-Agent: Agent roles, communication, collaboration workflow
- ✅ Proactive Monitoring: Health checks, alerts, remediation
- ✅ Integration: Both features coexisting

---

## 🚀 Future Enhancements

### Multi-Agent
- [ ] Agent learning (agents improve from past collaborations)
- [ ] Custom agent roles (user-defined specialists)
- [ ] Agent marketplace (share successful agent configurations)
- [ ] Parallel agent execution (speed up research/planning)
- [ ] Human-in-the-loop (ask user for decisions mid-collaboration)

### Proactive Monitoring
- [ ] Predictive monitoring (ML-based failure prediction)
- [ ] Performance baselines (detect anomalies automatically)
- [ ] Integration with cloud providers (AWS CloudWatch, GCP Monitoring)
- [ ] Mobile alerts (push notifications on critical issues)
- [ ] Monitoring dashboard (web UI for real-time status)

---

## 🎓 Learn More

- **Architecture**: See `packages/core/src/zenus_core/brain/multi_agent.py`
- **Monitoring**: See `packages/core/src/zenus_core/monitoring/proactive_monitor.py`
- **Tests**: See `packages/core/tests/test_multi_agent_and_monitoring.py`

---

**Last Updated**: 2026-02-26  
**Version**: 0.5.0-advanced
