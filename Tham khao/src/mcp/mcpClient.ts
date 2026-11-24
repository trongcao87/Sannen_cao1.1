import { McpLogEntry } from '../types/snvn';

export interface McpCallResponse<T = Record<string, unknown>> {
  ok: boolean;
  mode: 'live' | 'sandbox';
  result?: T;
  error?: string;
  logEntry: McpLogEntry;
}

let rpcSeq = 1;

/**
 * Invoke an AutoCAD 2022 MCP tool via JSON-RPC 2.0 over HTTP.
 * If sandboxMode is true OR live localhost connection is unreachable, provides clean fallback reporting.
 */
export async function invokeMcpTool<T = Record<string, unknown>>(
  endpoint: string,
  toolName: string,
  args: Record<string, unknown>,
  options: {
    useSandbox: boolean;
    sandboxHandler: () => T;
    summaryLabel: string;
  }
): Promise<McpCallResponse<T>> {
  const id = rpcSeq++;
  const timestamp = new Date().toLocaleTimeString('vi-VN', { hour12: false });
  const requestPayload = {
    jsonrpc: '2.0',
    id,
    method: 'tools/call',
    params: {
      name: toolName,
      arguments: args,
    },
  };

  if (options.useSandbox) {
    const simulated = options.sandboxHandler();
    const responsePayload = { jsonrpc: '2.0', id, result: simulated };
    return {
      ok: true,
      mode: 'sandbox',
      result: simulated,
      logEntry: {
        id: `log-${id}`,
        timestamp,
        method: toolName,
        mode: 'sandbox',
        status: 'ok',
        summary: `[Sandbox] ${options.summaryLabel}`,
        requestPayload,
        responsePayload,
      },
    };
  }

  try {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 5000);
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestPayload),
      signal: controller.signal,
    });
    window.clearTimeout(timer);

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status} — Không kết nối được cầu nối MCP tại ${endpoint}`);
    }

    const data = await resp.json();
    if (data.error) {
      throw new Error(data.error.message || 'Lỗi thực thi lệnh AutoCAD 2022');
    }

    return {
      ok: true,
      mode: 'live',
      result: data.result as T,
      logEntry: {
        id: `log-${id}`,
        timestamp,
        method: toolName,
        mode: 'live',
        status: 'ok',
        summary: `[AutoCAD 2022 Live] ${options.summaryLabel}`,
        requestPayload,
        responsePayload: data,
      },
    };
  } catch (err) {
    const message =
      err instanceof Error
        ? err.name === 'AbortError'
          ? `Quá thời gian chờ (5s) khi kết nối tới ${endpoint}. Hãy chạy Python ActiveX hoặc lệnh SNVN_MCP_START trên AutoCAD 2022.`
          : err.message
        : 'Không thể kết nối cầu nối MCP local';

    return {
      ok: false,
      mode: 'live',
      error: message,
      logEntry: {
        id: `log-${id}`,
        timestamp,
        method: toolName,
        mode: 'live',
        status: 'error',
        summary: message,
        requestPayload,
        responsePayload: { error: message },
      },
    };
  }
}
