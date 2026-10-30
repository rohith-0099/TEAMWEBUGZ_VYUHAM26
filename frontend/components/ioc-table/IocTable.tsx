"use client";

import { useMemo, useState } from "react";
import {
  Binary,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  FileCode,
  Globe,
  Hash,
  HelpCircle,
  KeyRound,
  Mail,
  Network,
  Search,
  Shield,
  ShieldAlert,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { safeDisplay } from "@/lib/defang";
import { useAnalysisStore } from "@/lib/store";
import type { IOC, IOCRole, IOCType } from "@/lib/types";

const ROLE_COLORS: Record<IOCRole, { bg: string; text: string; border: string }> = {
  c2: { bg: "bg-red-950/40", text: "text-red-400", border: "border-red-800/60" },
  payload: { bg: "bg-orange-950/40", text: "text-orange-400", border: "border-orange-800/60" },
  phishing: { bg: "bg-amber-950/40", text: "text-amber-400", border: "border-amber-800/60" },
  exfil: { bg: "bg-fuchsia-950/40", text: "text-fuchsia-400", border: "border-fuchsia-800/60" },
  victim: { bg: "bg-blue-950/40", text: "text-blue-400", border: "border-blue-800/60" },
  scanner: { bg: "bg-slate-800/50", text: "text-slate-300", border: "border-slate-700" },
  infrastructure: { bg: "bg-teal-950/40", text: "text-teal-400", border: "border-teal-800/60" },
  unknown: { bg: "bg-slate-900/60", text: "text-slate-400", border: "border-slate-800" },
};

const TYPE_ICONS: Record<IOCType, React.ElementType> = {
  ipv4: Network,
  ipv6: Network,
  domain: Globe,
  url: Globe,
  email: Mail,
  md5: Hash,
  sha1: Hash,
  sha256: Hash,
  sha512: Hash,
  cve: ShieldAlert,
  filepath: FileCode,
  registry: KeyRound,
  btc: Binary,
  other: HelpCircle,
};

interface IocTableProps {
  iocs?: IOC[];
}

export function IocTable({ iocs: propIocs }: IocTableProps) {
  const storeIocs = useAnalysisStore((state) => state.analysis.iocs);
  const selectTechnique = useAnalysisStore((state) => state.select);
  const iocs = propIocs || storeIocs || [];

  const [search, setSearch] = useState("");
  const [selectedRole, setSelectedRole] = useState<string>("all");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [showFiltered, setShowFiltered] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const activeIocs = useMemo(() => iocs.filter((i) => !i.filtered_reason), [iocs]);
  const filteredNoise = useMemo(() => iocs.filter((i) => Boolean(i.filtered_reason)), [iocs]);

  const uniqueRoles = useMemo(() => {
    return Array.from(new Set(activeIocs.map((i) => i.role)));
  }, [activeIocs]);

  const uniqueTypes = useMemo(() => {
    return Array.from(new Set(activeIocs.map((i) => i.type)));
  }, [activeIocs]);

  const displayedIocs = useMemo(() => {
    return activeIocs.filter((ioc) => {
      const matchesSearch =
        search === "" ||
        ioc.display.toLowerCase().includes(search.toLowerCase()) ||
        ioc.role.toLowerCase().includes(search.toLowerCase()) ||
        ioc.type.toLowerCase().includes(search.toLowerCase());
      const matchesRole = selectedRole === "all" || ioc.role === selectedRole;
      const matchesType = selectedType === "all" || ioc.type === selectedType;
      return matchesSearch && matchesRole && matchesType;
    });
  }, [activeIocs, search, selectedRole, selectedType]);

  const handleCopy = (ioc: IOC) => {
    const text = safeDisplay(ioc);
    navigator.clipboard.writeText(text);
    setCopiedId(ioc.id);
    toast.success(`Copied defanged indicator: ${text}`);
    setTimeout(() => setCopiedId(null), 1500);
  };

  return (
    <TooltipProvider delay={200}>
      <div className="flex flex-col gap-3 rounded-xl border bg-card/60 p-4 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <Shield className="size-4 text-primary" />
            <h2 className="font-heading text-sm font-semibold tracking-tight">
              Extracted Indicators of Compromise
            </h2>
            <Badge variant="outline" className="font-mono text-xs">
              {activeIocs.length} verified
            </Badge>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative w-44">
              <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search IOCs..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 pl-8 text-xs"
              />
            </div>

            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
              className="h-8 rounded-md border bg-background px-2 text-xs text-foreground"
            >
              <option value="all">All Roles</option>
              {uniqueRoles.map((r) => (
                <option key={r} value={r}>
                  {r.toUpperCase()}
                </option>
              ))}
            </select>

            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="h-8 rounded-md border bg-background px-2 text-xs text-foreground"
            >
              <option value="all">All Types</option>
              {uniqueTypes.map((t) => (
                <option key={t} value={t}>
                  {t.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* IOC Table */}
        <div className="overflow-x-auto rounded-lg border bg-background/60">
          <table className="w-full text-left text-xs">
            <thead className="border-b bg-muted/40 font-mono text-[11px] text-muted-foreground uppercase">
              <tr>
                <th className="py-2.5 pl-3 pr-2">Type</th>
                <th className="px-3 py-2.5">Indicator (Defanged)</th>
                <th className="px-3 py-2.5">Role</th>
                <th className="px-3 py-2.5">Confidence</th>
                <th className="px-3 py-2.5">Linked TTPs</th>
                <th className="py-2.5 pl-2 pr-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {displayedIocs.length > 0 ? (
                displayedIocs.map((ioc) => {
                  const Icon = TYPE_ICONS[ioc.type] || HelpCircle;
                  const roleStyle = ROLE_COLORS[ioc.role] || ROLE_COLORS.unknown;
                  const extConf = Math.round((ioc.confidence.extraction ?? 1) * 100);
                  const roleConf = ioc.confidence.role ? Math.round(ioc.confidence.role * 100) : null;

                  return (
                    <tr key={ioc.id} className="transition-colors hover:bg-muted/30">
                      <td className="py-2.5 pl-3 pr-2">
                        <span className="flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
                          <Icon className="size-3.5 text-primary/80" />
                          {ioc.type}
                        </span>
                      </td>

                      <td className="px-3 py-2.5 font-mono text-xs font-semibold text-foreground">
                        <Tooltip>
                          <TooltipTrigger
                            render={
                              <span className="cursor-help underline decoration-muted decoration-dotted underline-offset-4" />
                            }
                          >
                            {safeDisplay(ioc)}
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs text-xs">
                            <p className="font-semibold text-primary">Evidence quote:</p>
                            <p className="italic">
                              &ldquo;{ioc.evidence[0]?.quote || "Found in report body"}&rdquo;
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </td>

                      <td className="px-3 py-2.5">
                        <span
                          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase ${roleStyle.bg} ${roleStyle.text} ${roleStyle.border}`}
                        >
                          {ioc.role}
                        </span>
                      </td>

                      <td className="px-3 py-2.5">
                        <div className="flex flex-col gap-1 text-[10px]">
                          <div className="flex items-center gap-1 font-mono">
                            <span className="text-muted-foreground">ext:</span>
                            <span className="text-foreground">{extConf}%</span>
                          </div>
                          {roleConf !== null && (
                            <div className="flex items-center gap-1 font-mono">
                              <span className="text-muted-foreground">role:</span>
                              <span className="text-foreground">{roleConf}%</span>
                            </div>
                          )}
                        </div>
                      </td>

                      <td className="px-3 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {ioc.linked_techniques.length > 0 ? (
                            ioc.linked_techniques.map((tid) => (
                              <button
                                key={tid}
                                onClick={() => selectTechnique(tid)}
                                className="rounded border border-primary/30 bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] text-primary transition-colors hover:bg-primary/20"
                              >
                                {tid}
                              </button>
                            ))
                          ) : (
                            <span className="text-muted-foreground text-[11px]">—</span>
                          )}
                        </div>
                      </td>

                      <td className="py-2.5 pl-2 pr-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="size-7 p-0 text-muted-foreground hover:text-foreground"
                          onClick={() => handleCopy(ioc)}
                          title="Copy defanged indicator"
                        >
                          {copiedId === ioc.id ? (
                            <Check className="size-3.5 text-emerald-400" />
                          ) : (
                            <Copy className="size-3.5" />
                          )}
                        </Button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-xs text-muted-foreground">
                    No matching indicators found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Filtered Out Noise Accordion */}
        {filteredNoise.length > 0 && (
          <div className="rounded-lg border border-border/40 bg-muted/20">
            <button
              onClick={() => setShowFiltered(!showFiltered)}
              className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <span className="flex items-center gap-1.5">
                {showFiltered ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                Filtered Out Noise & Benign Lookalikes ({filteredNoise.length})
              </span>
              <span className="font-mono text-[10px]">
                Deterministic filter rule verification
              </span>
            </button>

            {showFiltered && (
              <div className="border-t px-3 py-2">
                <ul className="space-y-1.5 text-xs">
                  {filteredNoise.map((fn) => (
                    <li key={fn.id} className="flex items-center justify-between text-[11px]">
                      <span className="font-mono text-muted-foreground line-through">
                        {safeDisplay(fn)}
                      </span>
                      <span className="rounded bg-destructive/10 px-1.5 py-0.5 font-mono text-[10px] text-destructive">
                        dropped: {fn.filtered_reason}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
