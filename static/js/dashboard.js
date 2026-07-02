(() => {
  "use strict";

  const source = document.getElementById("dashboard-chart-data");
  if (!source) return;

  let charts;
  try {
    charts = JSON.parse(source.textContent || "{}");
  } catch (_error) {
    charts = {};
  }

  const palette = ["#10b981", "#6366f1", "#f59e0b", "#ec4899", "#06b6d4", "#8b5cf6", "#f43f5e", "#84cc16"];
  const instances = [];

  const roundedRect = (ctx, x, y, width, height, radius) => {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, r);
  };

  const shortLabel = (value, length = 14) => {
    const label = String(value ?? "");
    return label.length > length ? `${label.slice(0, length - 1)}…` : label;
  };
  const escapeHtml = value => String(value ?? "").replace(/[&<>"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]);

  class DashboardChart {
    constructor(canvas, config, key) {
      this.canvas = canvas;
      this.config = config || {};
      this.key = key;
      this.shell = canvas.closest(".chart-shell, .chart-shell-sm") || canvas.parentElement;
      this.tooltip = this.shell.querySelector(".chart-tooltip");
      this.hits = [];
      this.ctx = canvas.getContext("2d");
      this.resizeObserver = new ResizeObserver(() => this.draw());
      this.resizeObserver.observe(this.shell);
      canvas.addEventListener("mousemove", event => this.onPointer(event));
      canvas.addEventListener("mouseleave", () => this.hideTooltip());
      this.drawLegend();
      this.draw();
    }

    theme() {
      const dark = document.documentElement.classList.contains("dark");
      return {
        dark,
        text: dark ? "#94a3b8" : "#64748b",
        strong: dark ? "#e2e8f0" : "#0f172a",
        grid: dark ? "rgba(148,163,184,.13)" : "rgba(100,116,139,.13)",
        empty: dark ? "#64748b" : "#94a3b8",
      };
    }

    prepare() {
      const rect = this.shell.getBoundingClientRect();
      const width = Math.max(260, Math.floor(rect.width));
      const height = Math.max(210, Math.floor(rect.height));
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      this.canvas.width = width * dpr;
      this.canvas.height = height * dpr;
      this.canvas.style.width = `${width}px`;
      this.canvas.style.height = `${height}px`;
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.ctx.clearRect(0, 0, width, height);
      this.width = width;
      this.height = height;
      this.hits = [];
      this.colors = this.theme();
      this.ctx.font = "11px Inter, ui-sans-serif, system-ui";
      this.ctx.lineCap = "round";
      this.ctx.lineJoin = "round";
    }

    hasData() {
      return Array.isArray(this.config.datasets)
        && this.config.datasets.some(dataset => Array.isArray(dataset.data) && dataset.data.some(value => Number(value) !== 0));
    }

    draw() {
      this.prepare();
      if (!this.hasData()) {
        this.drawEmpty();
        return;
      }
      const type = this.config.type || "line";
      if (type === "line") this.drawLine();
      else if (type === "bar") this.drawBar();
      else if (type === "doughnut") this.drawDoughnut();
      else if (type === "radar") this.drawRadar();
    }

    drawEmpty() {
      const { ctx, width, height } = this;
      ctx.strokeStyle = this.colors.grid;
      ctx.lineWidth = 1;
      ctx.setLineDash([5, 6]);
      roundedRect(ctx, width / 2 - 48, height / 2 - 44, 96, 64, 16);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = this.colors.empty;
      ctx.textAlign = "center";
      ctx.font = "600 12px Inter, ui-sans-serif, system-ui";
      ctx.fillText("No data yet", width / 2, height / 2 + 38);
    }

    drawAxes(left, top, right, bottom, maxValue, suffix = "") {
      const { ctx } = this;
      const chartHeight = bottom - top;
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.font = "10px Inter, ui-sans-serif, system-ui";
      for (let index = 0; index <= 4; index += 1) {
        const ratio = index / 4;
        const y = bottom - chartHeight * ratio;
        ctx.strokeStyle = this.colors.grid;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(right, y);
        ctx.stroke();
        ctx.fillStyle = this.colors.text;
        ctx.fillText(`${Math.round(maxValue * ratio)}${suffix}`, left - 8, y);
      }
    }

    drawLine() {
      const { ctx, width, height, config } = this;
      const labels = config.labels || [];
      const datasets = config.datasets || [];
      const padding = { left: 46, right: 18, top: 18, bottom: 38 };
      const right = width - padding.right;
      const bottom = height - padding.bottom;
      const chartWidth = right - padding.left;
      const chartHeight = bottom - padding.top;
      const all = datasets.flatMap(dataset => dataset.data || []).map(Number);
      const maxValue = Number(config.max) || Math.max(1, ...all) * 1.12;
      this.drawAxes(padding.left, padding.top, right, bottom, maxValue, config.suffix || "");

      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = this.colors.text;
      labels.forEach((label, index) => {
        if (labels.length > 8 && index % 2) return;
        const x = padding.left + (labels.length === 1 ? chartWidth / 2 : chartWidth * index / Math.max(1, labels.length - 1));
        ctx.fillText(shortLabel(label, 12), x, bottom + 11);
      });

      datasets.forEach((dataset, datasetIndex) => {
        const color = dataset.color || palette[datasetIndex % palette.length];
        const points = (dataset.data || []).map((raw, index) => ({
          x: padding.left + (labels.length === 1 ? chartWidth / 2 : chartWidth * index / Math.max(1, labels.length - 1)),
          y: bottom - Math.min(maxValue, Math.max(0, Number(raw))) / maxValue * chartHeight,
          value: Number(raw),
          index,
        }));
        if (!points.length) return;

        if (datasetIndex === 0) {
          const gradient = ctx.createLinearGradient(0, padding.top, 0, bottom);
          gradient.addColorStop(0, `${color}38`);
          gradient.addColorStop(1, `${color}00`);
          ctx.beginPath();
          points.forEach((point, index) => index ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y));
          ctx.lineTo(points[points.length - 1].x, bottom);
          ctx.lineTo(points[0].x, bottom);
          ctx.closePath();
          ctx.fillStyle = gradient;
          ctx.fill();
        }

        ctx.beginPath();
        points.forEach((point, index) => index ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y));
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.stroke();
        points.forEach(point => {
          ctx.beginPath();
          ctx.arc(point.x, point.y, 3.5, 0, Math.PI * 2);
          ctx.fillStyle = this.colors.dark ? "#0f172a" : "#ffffff";
          ctx.fill();
          ctx.strokeStyle = color;
          ctx.lineWidth = 2;
          ctx.stroke();
          this.hits.push({ x: point.x, y: point.y, radius: 14, label: labels[point.index], dataset: dataset.label, value: point.value, color });
        });
      });
    }

    drawBar() {
      const { ctx, width, height, config } = this;
      const labels = config.labels || [];
      const datasets = config.datasets || [];
      const all = datasets.flatMap(dataset => dataset.data || []).map(Number);
      const maxValue = Number(config.max) || Math.max(1, ...all) * 1.15;
      const suffix = config.suffix || "";
      if (config.horizontal) {
        const left = Math.min(126, Math.max(80, width * .28));
        const right = width - 30;
        const top = 12;
        const bottom = height - 22;
        const groupHeight = (bottom - top) / Math.max(1, labels.length);
        labels.forEach((label, labelIndex) => {
          ctx.fillStyle = this.colors.text;
          ctx.textAlign = "right";
          ctx.textBaseline = "middle";
          ctx.fillText(shortLabel(label, 18), left - 9, top + groupHeight * (labelIndex + .5));
          datasets.forEach((dataset, datasetIndex) => {
            const slot = Math.min(15, groupHeight * .7 / Math.max(1, datasets.length));
            const y = top + groupHeight * labelIndex + (groupHeight - slot * datasets.length) / 2 + slot * datasetIndex;
            const value = Number(dataset.data[labelIndex] || 0);
            const barWidth = Math.max(2, (right - left) * Math.min(maxValue, value) / maxValue);
            const color = dataset.color || palette[datasetIndex % palette.length];
            ctx.fillStyle = this.colors.grid;
            roundedRect(ctx, left, y, right - left, Math.max(7, slot - 3), 5);
            ctx.fill();
            ctx.fillStyle = color;
            roundedRect(ctx, left, y, barWidth, Math.max(7, slot - 3), 5);
            ctx.fill();
            this.hits.push({ rect: { x: left, y, width: barWidth, height: Math.max(7, slot - 3) }, label, dataset: dataset.label, value, color });
          });
        });
        return;
      }

      const padding = { left: 43, right: 16, top: 15, bottom: 48 };
      const right = width - padding.right;
      const bottom = height - padding.bottom;
      const chartWidth = right - padding.left;
      const chartHeight = bottom - padding.top;
      this.drawAxes(padding.left, padding.top, right, bottom, maxValue, suffix);
      const groupWidth = chartWidth / Math.max(1, labels.length);
      const barWidth = Math.min(28, groupWidth * .72 / Math.max(1, datasets.length));
      labels.forEach((label, labelIndex) => {
        ctx.save();
        ctx.translate(padding.left + groupWidth * (labelIndex + .5), bottom + 9);
        ctx.rotate(labels.length > 6 ? -.35 : 0);
        ctx.fillStyle = this.colors.text;
        ctx.textAlign = labels.length > 6 ? "right" : "center";
        ctx.textBaseline = "top";
        ctx.fillText(shortLabel(label, 12), 0, 0);
        ctx.restore();
        datasets.forEach((dataset, datasetIndex) => {
          const value = Number(dataset.data[labelIndex] || 0);
          const barHeight = chartHeight * Math.min(maxValue, value) / maxValue;
          const x = padding.left + groupWidth * labelIndex + (groupWidth - barWidth * datasets.length) / 2 + barWidth * datasetIndex;
          const y = bottom - barHeight;
          const color = dataset.color || palette[datasetIndex % palette.length];
          const gradient = ctx.createLinearGradient(0, y, 0, bottom);
          gradient.addColorStop(0, color);
          gradient.addColorStop(1, `${color}99`);
          ctx.fillStyle = gradient;
          roundedRect(ctx, x + 1, y, Math.max(5, barWidth - 3), Math.max(2, barHeight), 6);
          ctx.fill();
          this.hits.push({ rect: { x, y, width: barWidth, height: barHeight }, label, dataset: dataset.label, value, color });
        });
      });
    }

    drawDoughnut() {
      const { ctx, width, height, config } = this;
      const labels = config.labels || [];
      const dataset = (config.datasets || [])[0] || { data: [] };
      const values = (dataset.data || []).map(Number);
      const total = values.reduce((sum, value) => sum + value, 0);
      const colors = dataset.colors || values.map((_, index) => palette[index % palette.length]);
      const centerX = width / 2;
      const centerY = height / 2 - 3;
      const outer = Math.min(width, height) * .34;
      const inner = outer * .67;
      let start = -Math.PI / 2;
      values.forEach((value, index) => {
        const angle = total ? value / total * Math.PI * 2 : 0;
        const end = start + angle;
        ctx.beginPath();
        ctx.arc(centerX, centerY, outer, start, end);
        ctx.arc(centerX, centerY, inner, end, start, true);
        ctx.closePath();
        ctx.fillStyle = colors[index];
        ctx.fill();
        this.hits.push({ arc: { centerX, centerY, inner, outer, start, end }, label: labels[index], dataset: dataset.label, value, color: colors[index] });
        start = end;
      });
      ctx.fillStyle = this.colors.strong;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = "800 26px Manrope, Inter, sans-serif";
      ctx.fillText(String(total), centerX, centerY - 4);
      ctx.fillStyle = this.colors.text;
      ctx.font = "10px Inter, sans-serif";
      ctx.fillText(dataset.label || "Total", centerX, centerY + 18);
    }

    drawRadar() {
      const { ctx, width, height, config } = this;
      const labels = config.labels || [];
      const dataset = (config.datasets || [])[0] || { data: [] };
      const values = (dataset.data || []).map(Number);
      const maxValue = Number(config.max) || Math.max(1, ...values);
      const centerX = width / 2;
      const centerY = height / 2 + 4;
      const radius = Math.min(width, height) * .31;
      const count = labels.length;
      if (count < 3) {
        this.drawEmpty();
        return;
      }
      const point = (index, ratio = 1) => {
        const angle = -Math.PI / 2 + index * Math.PI * 2 / count;
        return { x: centerX + Math.cos(angle) * radius * ratio, y: centerY + Math.sin(angle) * radius * ratio, angle };
      };
      for (let level = 1; level <= 4; level += 1) {
        ctx.beginPath();
        labels.forEach((_, index) => {
          const p = point(index, level / 4);
          index ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y);
        });
        ctx.closePath();
        ctx.strokeStyle = this.colors.grid;
        ctx.stroke();
      }
      labels.forEach((label, index) => {
        const edge = point(index);
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(edge.x, edge.y);
        ctx.strokeStyle = this.colors.grid;
        ctx.stroke();
        const labelPoint = point(index, 1.18);
        ctx.fillStyle = this.colors.text;
        ctx.textAlign = Math.cos(labelPoint.angle) > .25 ? "left" : Math.cos(labelPoint.angle) < -.25 ? "right" : "center";
        ctx.textBaseline = Math.sin(labelPoint.angle) > .4 ? "top" : Math.sin(labelPoint.angle) < -.4 ? "bottom" : "middle";
        ctx.fillText(shortLabel(label, 17), labelPoint.x, labelPoint.y);
      });
      const color = dataset.color || palette[0];
      const dataPoints = values.map((value, index) => ({ ...point(index, Math.min(maxValue, value) / maxValue), value, index }));
      ctx.beginPath();
      dataPoints.forEach((p, index) => index ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y));
      ctx.closePath();
      ctx.fillStyle = `${color}30`;
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();
      dataPoints.forEach(p => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        this.hits.push({ x: p.x, y: p.y, radius: 13, label: labels[p.index], dataset: dataset.label, value: p.value, color });
      });
    }

    drawLegend() {
      const target = document.querySelector(`[data-chart-legend="${this.key}"]`);
      if (!target) return;
      const config = this.config;
      const dataset = (config.datasets || [])[0] || {};
      let items;
      if (config.type === "doughnut") {
        const colors = dataset.colors || (config.labels || []).map((_, index) => palette[index % palette.length]);
        items = (config.labels || []).map((label, index) => ({ label, color: colors[index] }));
      } else {
        items = (config.datasets || []).map((item, index) => ({ label: item.label, color: item.color || palette[index % palette.length] }));
      }
      target.innerHTML = items.map(item => `<span class="chart-legend-item"><span class="chart-legend-dot" style="background:${item.color}"></span>${item.label || "Series"}</span>`).join("");
    }

    onPointer(event) {
      const rect = this.canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const hit = this.hits.find(item => {
        if (item.rect) return x >= item.rect.x && x <= item.rect.x + item.rect.width && y >= item.rect.y && y <= item.rect.y + item.rect.height;
        if (item.arc) {
          const dx = x - item.arc.centerX;
          const dy = y - item.arc.centerY;
          const distance = Math.sqrt(dx * dx + dy * dy);
          let angle = Math.atan2(dy, dx);
          if (angle < -Math.PI / 2) angle += Math.PI * 2;
          return distance >= item.arc.inner && distance <= item.arc.outer && angle >= item.arc.start && angle <= item.arc.end;
        }
        const dx = x - item.x;
        const dy = y - item.y;
        return Math.sqrt(dx * dx + dy * dy) <= (item.radius || 12);
      });
      if (!hit) {
        this.hideTooltip();
        return;
      }
      const suffix = this.config.suffix || "";
      this.tooltip.innerHTML = `<div class="font-semibold">${escapeHtml(hit.label)}</div><div class="mt-1 flex items-center gap-2 text-slate-300"><span class="h-2 w-2 rounded-full" style="background:${hit.color}"></span>${escapeHtml(hit.dataset || "Value")}: <strong class="text-white">${Number(hit.value).toLocaleString(undefined, { maximumFractionDigits: 1 })}${escapeHtml(suffix)}</strong></div>`;
      this.tooltip.style.left = `${x}px`;
      this.tooltip.style.top = `${y}px`;
      this.tooltip.classList.remove("hidden");
    }

    hideTooltip() {
      if (this.tooltip) this.tooltip.classList.add("hidden");
    }
  }

  document.querySelectorAll("canvas[data-dashboard-chart]").forEach(canvas => {
    const key = canvas.dataset.dashboardChart;
    instances.push(new DashboardChart(canvas, charts[key] || {}, key));
  });

  const clock = document.getElementById("dashboardClock");
  const updateClock = () => {
    if (!clock) return;
    clock.textContent = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date());
  };
  updateClock();
  window.setInterval(updateClock, 1000);

  new MutationObserver(() => instances.forEach(chart => chart.draw())).observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
})();
