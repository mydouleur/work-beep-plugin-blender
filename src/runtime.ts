// 绿色版路径与下载地址：版本目录与 scripts/fetch_blender.py 的 CATALOG 同步。
export const BLENDER_PLATFORM = "windows-x64";

export type CatalogTag = "recommended" | "lts";

export type CatalogEntry = {
    id: string;
    label: string;
    tags: CatalogTag[];
    /** false → UI / list 标 coming_soon，不可下载 */
    downloadable: boolean;
};

/** 与 fetch_blender.py CATALOG 字段对齐 */
export const BLENDER_CATALOG: readonly CatalogEntry[] = [
    { id: "5.2.1", label: "Blender 5.2.1", tags: ["recommended"], downloadable: true },
    { id: "4.5.13", label: "Blender 4.5 LTS", tags: ["lts"], downloadable: true },
    { id: "5.1.0", label: "Blender 5.1.0", tags: [], downloadable: true },
    { id: "4.3.2", label: "Blender 4.3.2", tags: [], downloadable: true },
] as const;

/** 推荐默认版本（catalog 里带 recommended 的那条） */
export const BLENDER_VERSION =
    BLENDER_CATALOG.find((e) => e.tags.includes("recommended"))?.id ?? "5.2.1";

function pack(version: string): string {
    return `blender-${version}-${BLENDER_PLATFORM}`;
}

/** resolveAsset 相对路径 → blender.exe（zip 自带一层同名目录） */
export function blenderExeRel(version: string = BLENDER_VERSION): string {
    const p = pack(version);
    return `runtime/${p}/${p}/blender.exe`;
}

export function blenderOuterRel(version: string = BLENDER_VERSION): string {
    return `runtime/${pack(version)}`;
}

export function blenderZipRel(version: string = BLENDER_VERSION): string {
    return `runtime/${pack(version)}.zip`;
}

export const MIRRORS = {
    aliyun: "https://mirrors.aliyun.com/blender/release",
    official: "https://download.blender.org/release",
    freedif: "https://mirror.freedif.org/blender/release",
} as const;

export type MirrorId = keyof typeof MIRRORS;

export function blenderZipUrl(version: string, mirror: MirrorId): string {
    const [major, minor] = version.split(".");
    return `${MIRRORS[mirror]}/Blender${major}.${minor}/${pack(version)}.zip`;
}

export function humanBytes(n: number): string {
    if (n <= 0) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let v = n;
    let i = 0;
    while (v >= 1024 && i < units.length - 1) {
        v /= 1024;
        i += 1;
    }
    return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
