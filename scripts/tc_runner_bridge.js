/**
 * GenX Leadership Academy — TC Runner Bridge
 * Injects test input data into n8n manual trigger without modifying workflow JSON or database state.
 */

const TARGET_WORKFLOW_ID = 'TSvKBGpM9nK7eb3U';

try {
  const workflowRunnerMod = require('/usr/local/lib/node_modules/n8n/dist/workflow-runner');
  const WorkflowRunner = workflowRunnerMod.WorkflowRunner;

  if (WorkflowRunner && WorkflowRunner.prototype) {
    const originalRun = WorkflowRunner.prototype.run;
    const originalResolvePinData = WorkflowRunner.prototype.resolvePinData;

    // Hook resolvePinData to ensure pinned data is always returned if present
    WorkflowRunner.prototype.resolvePinData = function (data) {
      if (data && data.pinData) {
        return data.pinData;
      }
      return originalResolvePinData.call(this, data);
    };

    // Hook run to enforce safety assertions and inject query via pinData
    WorkflowRunner.prototype.run = function (data, ...rest) {
      if (data && data.workflowData) {
        // SAFETY ASSERTION: Only the target retrieval workflow is permitted
        if (data.workflowData.id !== TARGET_WORKFLOW_ID) {
          throw new Error(
            `CRITICAL SAFETY VIOLATION: Execution blocked for unauthorized workflow '${data.workflowData.id}'. Only '${TARGET_WORKFLOW_ID}' is permitted.`
          );
        }

        const query = process.env.GENX_TEST_QUERY;
        if (!query || typeof query !== 'string' || query.trim().length === 0) {
          throw new Error(
            'SAFETY ASSERTION FAILED: Environment variable GENX_TEST_QUERY must be a non-empty string.'
          );
        }

        // Set executionMode to 'manual' so pinData resolution is active
        data.executionMode = 'manual';

        const triggerNodeName =
          (data.triggerToStartFrom && data.triggerToStartFrom.name) ||
          'When clicking ‘Execute workflow’';

        data.pinData = {
          [triggerNodeName]: [
            {
              json: {
                query: query.trim(),
              },
            },
          ],
        };

        console.error(
          `[BRIDGE] Successfully hooked WorkflowRunner for '${TARGET_WORKFLOW_ID}'`
        );
        console.error(
          `[BRIDGE] Injected pinData for trigger '${triggerNodeName}': query="${query.trim()}"`
        );
      }

      return originalRun.call(this, data, ...rest);
    };
  } else {
    console.error('[BRIDGE ERROR] WorkflowRunner prototype not found in module');
  }
} catch (err) {
  console.error('[BRIDGE INIT ERROR]', err);
}
