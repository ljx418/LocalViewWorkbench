import type { CleanupResult, ResourceSample } from "./types";

export function cleanupMessage(result: CleanupResult): string {
  if (result.verified && result.status === "released") return "已确认关闭本轮 LVW 模型服务并完成资源核对；下次分析前请启动模型服务。";
  if (result.verified && result.status === "noop") return "未发现已装载的 LVW 目标模型，无需清理。";
  if (result.status === "blocked") return "未执行清理：服务或其他模型不属于 LVW 可确认管理的范围。请在原服务中释放资源。";
  return "未能确认资源已释放，请检查服务后重试；不会显示为清理成功。";
}

export function sampleMessage(sample: ResourceSample | null): string {
  if (!sample?.values) return "GPU / 内存数值暂不可用";
  const v = sample.values;
  return `GPU 已用 ${v.gpu_used_mib} MiB / 可用 ${v.gpu_free_mib} MiB；运行环境可用内存 ${v.available_ram_mib} MiB`;
}
