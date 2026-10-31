"use client";
// Owner: Frontend B — see team/02_FRONTEND_B.md §7
// Globe / Map: deck.gl ScatterplotLayer + ArcLayer over MapLibre.
// NICE feature — only built after all other views are solid.

import React, { useEffect, useState } from "react";
import Map from "react-map-gl/maplibre";
import { DeckGL } from "@deck.gl/react";
import { ScatterplotLayer, ArcLayer } from "@deck.gl/layers";
import { setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { getGeo } from "@/lib/api";
import type { GeoPoint } from "@/lib/types";

const MAP_STYLE = "https://demotiles.maplibre.org/style.json";

// Turbopack breaks MapLibre's own worker path, so serve a copy from public/.
// Update public/maplibre-gl-worker.mjs whenever maplibre-gl is upgraded.
setWorkerUrl("/maplibre-gl-worker.mjs");

const IOC_ROLE_COLOR: Record<string, [number, number, number, number]> = {
  c2: [248, 113, 113, 230],
  payload: [251, 146, 60, 230],
  phishing: [251, 191, 36, 230],
  exfil: [232, 121, 249, 230],
  victim: [96, 165, 250, 230],
  scanner: [148, 163, 184, 230],
  infrastructure: [45, 212, 191, 230],
  unknown: [100, 116, 139, 230],
};

function roleColor(role: string): [number, number, number, number] {
  return IOC_ROLE_COLOR[role] ?? IOC_ROLE_COLOR.unknown;
}

const INITIAL_VIEW = {
  longitude: 10,
  latitude: 30,
  zoom: 1.5,
  pitch: 30,
  bearing: 0,
};

export function GlobeView({ analysisId }: { analysisId: string }) {
  const [points, setPoints] = useState<GeoPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; point: GeoPoint } | null>(null);

  useEffect(() => {
    getGeo(analysisId)
      .then((geo) => {
        setPoints(geo.points);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [analysisId]);

  // find a victim point for arcs
  const victimPoint = points.find((p) => p.role === "victim");

  const scatterLayer = new ScatterplotLayer<GeoPoint>({
    id: "ioc-scatter",
    data: points,
    getPosition: (p) => [p.lon, p.lat],
    getRadius: 30000,
    getFillColor: (p) => roleColor(p.role),
    pickable: true,
    radiusMinPixels: 6,
    radiusMaxPixels: 20,
    onHover: (info) => {
      if (info.object) {
        setTooltip({ x: info.x, y: info.y, point: info.object as GeoPoint });
      } else {
        setTooltip(null);
      }
    },
  });

  const arcLayer = victimPoint
    ? new ArcLayer<GeoPoint>({
        id: "ioc-arcs",
        data: points.filter((p) => p.role !== "victim" && (p.role === "c2" || p.role === "exfil")),
        getSourcePosition: (p) => [p.lon, p.lat],
        getTargetPosition: () => [victimPoint.lon, victimPoint.lat],
        getSourceColor: (p) => roleColor(p.role),
        getTargetColor: [96, 165, 250, 180],
        getWidth: 2,
        pickable: false,
      })
    : null;

  const layers = arcLayer ? [scatterLayer, arcLayer] : [scatterLayer];

  if (loading) {
    return (
      <div
        style={{
          height: 500,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#000000",
          color: "#8A8A93",
          fontFamily: "var(--font-sans, Inter, sans-serif)",
        }}
      >
        Loading map…
      </div>
    );
  }

  if (points.length === 0) {
    return (
      <div
        style={{
          height: 500,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#000000",
          color: "#8A8A93",
          fontFamily: "var(--font-sans, Inter, sans-serif)",
        }}
      >
        No geolocated IOCs for this report.
      </div>
    );
  }

  return (
    <div style={{ position: "relative", height: 500, borderRadius: 8, overflow: "hidden" }}>
      <DeckGL
        initialViewState={INITIAL_VIEW}
        controller
        layers={layers}
        style={{ position: "absolute", inset: "0" }}
      >
        <Map mapStyle={MAP_STYLE} />
      </DeckGL>

      {/* tooltip */}
      {tooltip && (
        <div
          style={{
            position: "absolute",
            left: tooltip.x + 12,
            top: tooltip.y - 10,
            background: "#0A0A0AEE",
            border: "1px solid #1F1F1F",
            borderRadius: 6,
            padding: "6px 10px",
            fontSize: 11,
            color: "#F5F5F7",
            pointerEvents: "none",
            fontFamily: "var(--font-sans, Inter, sans-serif)",
            zIndex: 10,
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-mono, monospace)",
              color: "#22F0FF",
              marginBottom: 2,
            }}
          >
            {tooltip.point.display}
          </div>
          <div>{tooltip.point.country}{tooltip.point.city ? ` · ${tooltip.point.city}` : ""}</div>
          <div style={{ color: "#8A8A93", marginTop: 2 }}>Role: {tooltip.point.role}</div>
        </div>
      )}

      {/* legend */}
      <div
        style={{
          position: "absolute",
          bottom: 12,
          left: 12,
          background: "#0A0A0AEE",
          border: "1px solid #1F1F1F",
          borderRadius: 6,
          padding: "8px 10px",
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          fontSize: 10,
          zIndex: 10,
        }}
      >
        {Object.entries(IOC_ROLE_COLOR).map(([role, rgba]) => (
          <div key={role} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: `rgba(${rgba[0]},${rgba[1]},${rgba[2]},0.9)`,
              }}
            />
            <span style={{ color: "#8A8A93", textTransform: "capitalize" }}>{role}</span>
          </div>
        ))}
      </div>

      {/* disclaimer */}
      <div
        style={{
          position: "absolute",
          bottom: 12,
          right: 12,
          fontSize: 9,
          color: "#8A8A93",
          background: "#0A0A0ACC",
          borderRadius: 4,
          padding: "3px 6px",
          zIndex: 10,
          maxWidth: 220,
          textAlign: "right",
        }}
      >
        Location from offline IP geolocation (DB-IP Lite). IP location ≠ attacker location.
      </div>
    </div>
  );
}
