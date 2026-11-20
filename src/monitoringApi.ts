export type SourceType = "LIVE_HARDWARE" | "RECORDED_HARDWARE" | "SYNTHETIC_SIMULATION";

export interface DetectionRecord {
  event_id: string;
  capture_id: string | null;
  timestamp: string | null;
  timestamp_epoch: number | null;
  modality: "RF" | "ACOUSTIC";
  source_type: SourceType | null;
  detection_type: string | null;
  detection_status: string | null;
  sensor_id: string | null;
  confidence_score: number | null;
  metrics: Record<string, number | string>;
  evidence_ref: string | null;
  verification_status: string | null;
}

export interface SensorSnapshot {
  sensor_id: string;
  connected: boolean;
  status: string;
  source_type: SourceType | null;
  processed_count: number;
  metrics: Record<string, number | null>;
  morse_status?: string | null;
}

export interface MonitoringSnapshot {
  schema_version: number;
  server_status: string;
  updated_at: string;
  monitoring: {
    status: string;
    running: boolean;
    paused: boolean;
    uptime_sec: number;
  };
  rf: SensorSnapshot;
  acoustic: SensorSnapshot;
  summary: {
    total_detections: number;
    active_alerts: number;
    latest_detection_timestamp: string | null;
  };
  detections: DetectionRecord[];
}

export type MonitoringAction = "start" | "pause" | "resume" | "stop";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}

function isSensorSnapshot(value: unknown): value is SensorSnapshot {
  return (
    isRecord(value) &&
    typeof value.sensor_id === "string" &&
    typeof value.connected === "boolean" &&
    typeof value.status === "string" &&
    (value.source_type === null ||
      value.source_type === "LIVE_HARDWARE" ||
      value.source_type === "RECORDED_HARDWARE" ||
      value.source_type === "SYNTHETIC_SIMULATION") &&
    typeof value.processed_count === "number" &&
    Number.isFinite(value.processed_count) &&
    isRecord(value.metrics) &&
    Object.values(value.metrics).every(isNullableNumber) &&
    (value.morse_status === undefined || isNullableString(value.morse_status))
  );
}

function isDetectionRecord(value: unknown): value is DetectionRecord {
  return (
    isRecord(value) &&
    typeof value.event_id === "string" &&
    (value.modality === "RF" || value.modality === "ACOUSTIC") &&
    isNullableString(value.capture_id) &&
    isNullableString(value.timestamp) &&
    isNullableNumber(value.timestamp_epoch) &&
    (value.source_type === null ||
      value.source_type === "LIVE_HARDWARE" ||
      value.source_type === "RECORDED_HARDWARE" ||
      value.source_type === "SYNTHETIC_SIMULATION") &&
    isNullableString(value.detection_type) &&
    isNullableString(value.detection_status) &&
    isNullableString(value.sensor_id) &&
    isNullableNumber(value.confidence_score) &&
    (value.confidence_score === null || (value.confidence_score >= 0 && value.confidence_score <= 1)) &&
    isRecord(value.metrics) &&
    Object.values(value.metrics).every((metric) => typeof metric === "string" || (typeof metric === "number" && Number.isFinite(metric))) &&
    isNullableString(value.evidence_ref) &&
    isNullableString(value.verification_status)
  );
}

function parseSnapshot(value: unknown): MonitoringSnapshot {
  if (
    !isRecord(value) ||
    !isRecord(value.monitoring) ||
    !isSensorSnapshot(value.rf) ||
    !isSensorSnapshot(value.acoustic) ||
    !isRecord(value.summary) ||
    !Array.isArray(value.detections) ||
    typeof value.schema_version !== "number" ||
    typeof value.server_status !== "string" ||
    typeof value.updated_at !== "string" ||
    typeof value.monitoring.status !== "string" ||
    typeof value.monitoring.running !== "boolean" ||
    typeof value.monitoring.paused !== "boolean" ||
    typeof value.monitoring.uptime_sec !== "number" ||
    !Number.isFinite(value.monitoring.uptime_sec) ||
    typeof value.summary.total_detections !== "number" ||
    typeof value.summary.active_alerts !== "number" ||
    !isNullableString(value.summary.latest_detection_timestamp) ||
    !value.detections.every(isDetectionRecord)
  ) {
    throw new Error("Monitoring API returned an invalid response.");
  }

  const seen = new Set<string>();
  const detections = (value.detections as DetectionRecord[]).filter((record) => {
    if (seen.has(record.event_id)) return false;
    seen.add(record.event_id);
    return true;
  });

  return { ...value, detections } as MonitoringSnapshot;
}

async function requestJson(url: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(url, {
    cache: "no-store",
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let message = `Monitoring API request failed (${response.status}).`;
    try {
      const body: unknown = await response.json();
      if (isRecord(body) && typeof body.error === "string") {
        message = body.error;
      }
    } catch {
      // Keep the HTTP status as the actionable error when there is no JSON body.
    }
    throw new Error(message);
  }
  return response.json();
}

export async function fetchMonitoringSnapshot(): Promise<MonitoringSnapshot> {
  return parseSnapshot(await requestJson("/api/monitoring"));
}

export async function sendMonitoringAction(action: MonitoringAction): Promise<MonitoringSnapshot> {
  return parseSnapshot(
    await requestJson(`/api/monitoring/${action}`, {
      method: "POST",
    }),
  );
}
