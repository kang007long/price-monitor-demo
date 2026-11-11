"use client";

import { useId, useMemo, useState } from "react";

import { formatMoney, formatShortDate } from "@/lib/format";
import type { HistoryPoint } from "@/lib/types";

const WIDTH = 560;
const HEIGHT = 240;
const PAD = { top: 16, right: 14, bottom: 28, left: 52 };

interface Props {
  points: HistoryPoint[];
  currency?: string;
}

export function PriceChart({ points, currency = "GBP" }: Props) {
  const gradientId = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [hover, setHover] = useState<number | null>(null);

  const data = useMemo(
    () => points.filter((point) => point.price !== null),
    [points],
  );

  const geometry = useMemo(() => {
    if (data.length < 2) return null;
    const prices = data.map((point) => point.price as number);
    const sources = data
      .map((point) => point.sourcePrice)
      .filter((value): value is number => value !== null);
    const values = [...prices, ...sources];
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) {
      min -= 1;
      max += 1;
    }
    const padding = (max - min) * 0.12;
    min = Math.max(0, min - padding);
    max += padding;

    const plotWidth = WIDTH - PAD.left - PAD.right;
    const plotHeight = HEIGHT - PAD.top - PAD.bottom;
    const step = plotWidth / (data.length - 1);
    const xFor = (index: number) => PAD.left + index * step;
    const yFor = (value: number) =>
      PAD.top + plotHeight - ((value - min) / (max - min)) * plotHeight;

    const line = data
      .map((point, index) => {
        const command = index === 0 ? "M" : "L";
        return `${command}${xFor(index).toFixed(1)},${yFor(point.price as number).toFixed(1)}`;
      })
      .join(" ");
    const area = `${line} L${xFor(data.length - 1).toFixed(1)},${(
      PAD.top + plotHeight
    ).toFixed(1)} L${PAD.left},${(PAD.top + plotHeight).toFixed(1)} Z`;

    const sourceLine = data
      .map((point, index) => {
        if (point.sourcePrice === null) return "";
        const value = yFor(point.sourcePrice).toFixed(1);
        return `${index === 0 ? "M" : "L"}${xFor(index).toFixed(1)},${value}`;
      })
      .filter(Boolean)
      .join(" ");

    const ticks = [0, 0.5, 1].map((ratio) => {
      const value = min + (max - min) * ratio;
      return { value, y: yFor(value) };
    });

    return {
      min,
      max,
      plotWidth,
      plotHeight,
      step,
      xFor,
      yFor,
      line,
      area,
      sourceLine,
      ticks,
      lastX: xFor(data.length - 1),
      floorY: PAD.top + plotHeight,
    };
  }, [data]);

  if (!geometry || data.length < 2) {
    return <div className="chart-empty">Not enough history to draw a trend yet.</div>;
  }

  const active = hover !== null ? data[hover] : null;
  const activeIndex = hover;
  const activeX = activeIndex !== null ? geometry.xFor(activeIndex) : 0;
  const activeY = active ? geometry.yFor(active.price as number) : 0;

  function onMove(event: React.PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * WIDTH;
    const index = Math.round((x - PAD.left) / geometry!.step);
    setHover(Math.max(0, Math.min(data.length - 1, index)));
  }

  const labelIndexes = [0, Math.floor((data.length - 1) / 2), data.length - 1].filter(
    (value, index, all) => all.indexOf(value) === index,
  );

  return (
    <div className="chart-wrap">
      <svg
        className="chart-svg"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Price history from ${data[0].date} to ${data[data.length - 1].date}. Use the history table below for exact values.`}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" className="chart-gradient-stop" stopOpacity="0.22" />
            <stop offset="100%" className="chart-gradient-stop" stopOpacity="0.01" />
          </linearGradient>
        </defs>

        {geometry.ticks.map((tick) => (
          <g key={tick.y}>
            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={tick.y}
              y2={tick.y}
              className="chart-grid"
              strokeWidth="1"
            />
            <text x={PAD.left - 9} y={tick.y + 3.5} textAnchor="end">
              {formatMoney(tick.value, currency)}
            </text>
          </g>
        ))}

        <path d={geometry.area} fill={`url(#${gradientId})`} />
        {geometry.sourceLine && (
          <path
            d={geometry.sourceLine}
            className="chart-source"
            fill="none"
            strokeWidth="1.4"
            strokeDasharray="4 4"
            opacity="0.85"
          />
        )}
        <path
          d={geometry.line}
          className="chart-line"
          fill="none"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle
          cx={geometry.lastX}
          cy={geometry.yFor(data[data.length - 1].price as number)}
          r="3.5"
          className="chart-last-dot"
          strokeWidth="2"
        />

        {labelIndexes.map((index) => (
          <text
            key={index}
            x={geometry.xFor(index)}
            y={HEIGHT - 8}
            textAnchor={index === 0 ? "start" : index === data.length - 1 ? "end" : "middle"}
          >
            {formatShortDate(data[index].date)}
          </text>
        ))}

        {activeIndex !== null && active && (
          <g>
            <line
              x1={activeX}
              x2={activeX}
              y1={PAD.top}
              y2={geometry.floorY}
              className="chart-crosshair"
              strokeWidth="1"
            />
            <circle
              cx={activeX}
              cy={activeY}
              r="4.5"
              className="chart-hover-dot"
              strokeWidth="2"
            />
          </g>
        )}
      </svg>

      {active && (
        <div
          className="chart-tooltip"
          style={{
            left: `${Math.min(86, Math.max(14, (activeX / WIDTH) * 100))}%`,
            top: `${Math.max(30, (activeY / HEIGHT) * 100)}%`,
          }}
        >
          <strong>{formatMoney(active.price, currency)}</strong>
          <div>{formatShortDate(active.date)}</div>
          <div className="chart-tooltip-source">
            Source {formatMoney(active.sourcePrice, currency)}
          </div>
        </div>
      )}
    </div>
  );
}
