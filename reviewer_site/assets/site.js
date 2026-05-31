(function () {
  "use strict";

  const DATA_URL = "data/site-data.json";
  const DATABASE_RESULT_LIMIT = 10;
  const QA_RESULT_LIMIT = 3;

  const metricCards = [
    ["seedStructures", "Seed structures", "Initial 2D semiconductor structures"],
    ["seedChannels", "Seed channels", "Carrier-direction mobility channels"],
    ["qcPassedSeedMaterials", "QC-passed seed materials", "Materials retained after seed QC"],
    ["retainedSeedLabels", "Retained seed labels", "Reliability-gated seed feedback"],
    ["generatedStructures", "Generated structures", "Campaign-scale generated pool"],
    ["deduplicatedSubmittedCandidates", "DFT candidates", "Deduplicated submitted representatives"],
    ["retainedGeneratedFormulas", "Generated formulas retained", "Generated materials passing the reliability gate"],
    ["totalRetainedLabels", "Total retained labels", "Seed plus generated feedback labels"],
  ];

  const state = {
    data: null,
    candidateSort: { key: "bestMobility", direction: "desc" },
    databaseTable: "all",
    selectedFigure: 0,
  };

  const $ = (selector) => document.querySelector(selector);

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatNumber(value) {
    return Number(value).toLocaleString("en-US");
  }

  function formatCompact(value) {
    const number = Number(value);
    if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}M`;
    if (number >= 1_000) return `${(number / 1_000).toFixed(1)}k`;
    return formatNumber(number);
  }

  function formatMetricValue(key, value) {
    if (key === "generatedStructures") return formatCompact(value);
    return formatNumber(value);
  }

  function formatDecimal(value, digits = 2) {
    return Number(value).toLocaleString("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function mobilityUnit() {
    return state.data?.units?.mobility || "cm² V⁻¹ s⁻¹";
  }

  function formatMobility(value) {
    if (value === null || value === undefined || value === "") return "not available";
    const number = Number(value);
    if (!Number.isFinite(number)) return escapeHtml(value);
    if (number >= 1000) return `${formatNumber(Math.round(number))} ${mobilityUnit()}`;
    return `${formatDecimal(number, 1)} ${mobilityUnit()}`;
  }

  function percent(value) {
    return `${formatDecimal(Number(value) * 100, 1)}%`;
  }

  function asText(value) {
    return String(value ?? "").toLowerCase();
  }

  function renderMetricGrid(data) {
    const metrics = data.metrics;
    $("#metric-grid").innerHTML = metricCards
      .map(([key, label, note]) => {
        return `
          <article class="metric-card">
            <div class="value">${escapeHtml(formatMetricValue(key, metrics[key]))}</div>
            <div>
              <p class="label">${escapeHtml(label)}</p>
              <p class="note">${escapeHtml(note)}</p>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderHeader(data) {
    $("#campaign-headline").textContent = data.primaryStory.headline;
    $("#abstract-text").textContent = data.primaryStory.summary;
    $("#site-version").textContent = `${data.sourcePackage} / ${data.siteVersion}`;
  }

  function renderFunnel(data) {
    const rows = data.funnel;
    const maxLog = Math.max(...rows.map((row) => Math.log10(row.count + 1)));
    $("#funnel-chart").innerHTML = rows
      .map((row, index) => {
        const width = Math.max(5, (Math.log10(row.count + 1) / maxLog) * 100);
        const note = funnelNote(data, index, row);
        return `
          <div class="funnel-row">
            <div>
              <div class="funnel-label">${escapeHtml(row.stage)}</div>
              <div class="funnel-ratio">${escapeHtml(note)}</div>
            </div>
            <div class="funnel-track" aria-hidden="true">
              <div class="funnel-bar" style="width: ${width}%"></div>
            </div>
            <div class="funnel-value">${escapeHtml(formatNumber(row.count))}</div>
          </div>
        `;
      })
      .join("");
  }

  function funnelNote(data, index, row) {
    if (index === 0) return "Generated campaign pool";
    if (row.stage === "DFT validation candidates") {
      return `${percent(row.count / data.metrics.generatedStructures)} of generated structures`;
    }
    if (row.stage === "Retained generated formulas") {
      return `${percent(row.count / data.metrics.deduplicatedSubmittedCandidates)} of DFT candidates`;
    }
    if (row.stage === "Trusted generated channels") {
      return "Carrier-direction channels retained from generated candidates";
    }
    if (row.stage === "Total retained feedback labels") {
      return `${formatNumber(data.metrics.retainedSeedLabels)} seed labels + ${formatNumber(data.metrics.trustedGeneratedChannels)} generated channels`;
    }
    return "";
  }

  function renderAlignn(data) {
    const alignn = data.alignn;
    $("#alignn-panel").innerHTML = `
      <div class="alignn-header">
        <div>
          <h3>ALIGNN role: ${escapeHtml(alignn.role)}</h3>
          <p>Used for acquisition ranking over seed materials. Error metrics are reported on ${escapeHtml(data.units.alignnErrorScale)}, not as final mobility labels.</p>
        </div>
      </div>
      <div class="mini-stat-grid">
        ${miniStat("Seed materials", formatNumber(alignn.nMaterials))}
        ${miniStat("OOF predictions", formatNumber(alignn.nOofPredictions))}
        ${miniStat("Spearman ρ", formatDecimal(alignn.spearmanRho, 3))}
        ${miniStat("Kendall τ", formatDecimal(alignn.kendallTau, 3))}
        ${miniStat("MAE (log10 mobility)", formatDecimal(alignn.mae, 3))}
        ${miniStat("RMSE (log10 mobility)", formatDecimal(alignn.rmse, 3))}
      </div>
    `;
  }

  function miniStat(label, value) {
    return `
      <div class="mini-stat">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `;
  }

  function renderCandidateHighlights(data) {
    $("#candidate-highlights").innerHTML = data.topCandidates
      .slice(0, 4)
      .map((candidate) => {
        return `
          <article class="candidate-card">
            <h3>${escapeHtml(candidate.formula)}</h3>
            <div class="mobility">${escapeHtml(formatMobility(candidate.bestMobility))}</div>
            <p>${escapeHtml(candidate.bestCarrier)} / ${escapeHtml(candidate.bestChannel)}</p>
            <div class="tag-row">
              <span class="tag">${escapeHtml(candidate.usableChannelCount)} trusted channels</span>
              <span class="tag">${escapeHtml(candidate.structureClusterId)}</span>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function getFilteredCandidates() {
    const data = state.data;
    const query = asText($("#candidate-search").value).trim();
    const carrier = $("#carrier-filter").value;
    const minMobility = Number($("#mobility-filter").value);

    return data.retainedMaterials
      .filter((candidate) => {
        const haystack = [
          candidate.formula,
          candidate.bestCarrier,
          candidate.bestChannel,
          candidate.structureClusterId,
          candidate.materialId,
        ]
          .map(asText)
          .join(" ");
        const matchesQuery = !query || haystack.includes(query);
        const matchesCarrier = carrier === "all" || candidate.bestCarrier === carrier;
        const matchesMobility = Number(candidate.bestMobility) >= minMobility;
        return matchesQuery && matchesCarrier && matchesMobility;
      })
      .sort(compareCandidates);
  }

  function compareCandidates(a, b) {
    const { key, direction } = state.candidateSort;
    const left = a[key];
    const right = b[key];
    const multiplier = direction === "asc" ? 1 : -1;
    if (typeof left === "number" && typeof right === "number") {
      return (left - right) * multiplier;
    }
    return String(left).localeCompare(String(right), undefined, { numeric: true }) * multiplier;
  }

  function renderCandidateTable() {
    const rows = getFilteredCandidates();
    $("#candidate-count").textContent = `${rows.length} of ${state.data.retainedMaterials.length} retained generated formulas shown`;
    $("#candidate-table-body").innerHTML = rows
      .map((candidate) => {
        return `
          <tr title="${escapeHtml(candidate.materialId)}">
            <td><strong>${escapeHtml(candidate.formula)}</strong></td>
            <td class="numeric">${escapeHtml(formatMobility(candidate.bestMobility))}</td>
            <td>${escapeHtml(candidate.bestCarrier)}</td>
            <td>${escapeHtml(candidate.bestChannel)}</td>
            <td class="numeric">${escapeHtml(candidate.usableChannelCount)}</td>
            <td>${escapeHtml(candidate.structureClusterId)}</td>
          </tr>
        `;
      })
      .join("");
  }

  function bindCandidateControls() {
    $("#candidate-search").addEventListener("input", renderCandidateTable);
    $("#carrier-filter").addEventListener("change", renderCandidateTable);
    $("#mobility-filter").addEventListener("change", renderCandidateTable);
    document.querySelectorAll("[data-sort]").forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.dataset.sort;
        const sameKey = state.candidateSort.key === key;
        state.candidateSort = {
          key,
          direction: sameKey && state.candidateSort.direction === "desc" ? "asc" : "desc",
        };
        renderCandidateTable();
      });
    });
  }

  function evidenceSectionLabel(tableName) {
    return state.data?.databaseSearch?.tables?.[tableName]?.section || tableName.replaceAll("_", " ");
  }

  function renderDatabaseSearch(data) {
    const database = data.databaseSearch;
    const tableEntries = Object.entries(database.tables);
    $("#database-summary").innerHTML = `
      <div class="database-source">
        <strong>${escapeHtml(formatNumber(database.totalIndexedRows))}</strong>
        <span>searchable evidence records from the manuscript snapshot</span>
      </div>
      <div class="database-chips">
        ${tableEntries
          .map(([, meta]) => `<span class="db-chip">${escapeHtml(meta.section)}: ${escapeHtml(formatNumber(meta.rowCount))}</span>`)
          .join("")}
      </div>
    `;
    $("#database-table-filter").innerHTML = [
      `<option value="all">All evidence sections</option>`,
      ...tableEntries.map(([name, meta]) => {
        return `<option value="${escapeHtml(name)}">${escapeHtml(meta.section)} (${escapeHtml(formatNumber(meta.rowCount))})</option>`;
      }),
    ].join("");
    renderDatabaseResults();
  }

  function getDatabaseResults() {
    const query = asText($("#database-search").value).trim();
    const table = $("#database-table-filter").value;
    return state.data.databaseSearch.records.filter((record) => {
      const matchesTable = table === "all" || record.table === table;
      const matchesQuery = !query || record.searchText.includes(query);
      return matchesTable && matchesQuery;
    });
  }

  function renderDatabaseResults() {
    const rows = getDatabaseResults();
    const shown = rows.slice(0, DATABASE_RESULT_LIMIT);
    const table = $("#database-table-filter").value;
    const sectionText = table === "all" ? "all evidence sections" : evidenceSectionLabel(table);
    $("#database-count").textContent = `${formatNumber(rows.length)} matches across ${sectionText}; showing ${formatNumber(shown.length)}.`;
    $("#database-results").innerHTML = shown.map(renderDatabaseRecord).join("");
  }

  function renderDatabaseRecord(record) {
    const fieldEntries = Object.entries(record.fields)
      .filter(([, value]) => value !== null && value !== "")
      .slice(0, 8);
    return `
      <article class="db-result">
        <div class="db-result-head">
          <span class="db-table">${escapeHtml(record.section)}</span>
          <h3>${escapeHtml(record.label)}</h3>
        </div>
        <p>${escapeHtml(record.summary)}</p>
        <dl>
          ${fieldEntries
            .map(([key, value]) => {
              return `<div><dt>${escapeHtml(formatFieldLabel(key))}</dt><dd>${escapeHtml(formatDatabaseFieldValue(key, value))}</dd></div>`;
            })
            .join("")}
        </dl>
      </article>
    `;
  }

  function formatFieldLabel(key) {
    return key
      .replace(/_cm2_vs$/i, "")
      .replace(/_cm2_vs_/i, " ")
      .replace(/_cm2_vs/i, "")
      .replace(/_cm2_Vs/g, "")
      .replace(/r2/gi, "R²")
      .replaceAll("_", " ");
  }

  function formatDatabaseFieldValue(key, value) {
    if (/mobility_cm2_vs|mobility_cm2_Vs|best_dft_mobility/i.test(key)) {
      return formatMobility(value);
    }
    if (/fit_r2|minimum_fit/i.test(key) && Number.isFinite(Number(value))) {
      return formatDecimal(value, 3);
    }
    return String(value);
  }

  function bindDatabaseControls() {
    $("#database-search").addEventListener("input", renderDatabaseResults);
    $("#database-table-filter").addEventListener("change", renderDatabaseResults);
  }

  function hasCjk(value) {
    return /[\u3400-\u9fff]/.test(String(value));
  }

  function qaTerms(question) {
    const query = asText(question);
    const terms = query
      .split(/[^a-z0-9]+/i)
      .map((term) => term.trim())
      .filter((term) => term.length > 2 && !["the", "and", "for", "with", "this", "that"].includes(term));

    const add = (...items) => terms.push(...items);
    if (/讲了什么|是什么|about|overview|summary|main|paper/.test(query)) {
      add("invdesmobility", "first-principles", "mobility", "feedback", "inverse", "design", "semiconductors", "reliability");
    }
    if (/贡献|contribution|novel|main finding/.test(query)) {
      add("framework", "database", "feedback", "generated", "retained", "campaign");
    }
    if (/alignn|ranker|ranking|acquisition|排序/.test(query)) {
      add("alignn", "acquisition", "ranker", "enrichment", "top-decile", "queue");
    }
    if (/reliability|gate|qc|quality|可靠|筛选|过滤|质量/.test(query)) {
      add("reliability", "gate", "retained", "withheld", "quality", "feedback", "channel");
    }
    if (/candidate|generated|screen|筛选|候选|生成|材料/.test(query)) {
      add("generated", "candidate", "screening", "structures", "phonon", "validation", "retained");
    }
    return [...new Set(terms)];
  }

  function scoreQaChunk(question, chunk) {
    const query = asText(question);
    const terms = qaTerms(question);
    const haystack = chunk.searchText || asText(`${chunk.source} ${chunk.section} ${chunk.title} ${chunk.text}`);
    let score = 0;

    terms.forEach((term) => {
      if (haystack.includes(term)) score += term.length > 5 ? 3 : 1;
      if (asText(chunk.title).includes(term)) score += 3;
      if (asText(chunk.section).includes(term)) score += 2;
    });

    if (/讲了什么|about|overview|summary|paper/.test(query)) {
      if (chunk.section === "Abstract") score += 9;
      if (["Introduction", "Discussion"].includes(chunk.section)) score += 5;
      if (chunk.title === "Closed-loop validation" || chunk.title === "Reliability-gated generated candidates") score += 4;
    }
    if (/alignn|ranker|acquisition|排序/.test(query) && haystack.includes("alignn")) score += 7;
    if (/reliability|gate|qc|可靠|质量/.test(query) && haystack.includes("reliability")) score += 7;
    if (/candidate|generated|screen|候选|生成/.test(query) && haystack.includes("generated")) score += 7;

    return score;
  }

  function getQaMatches(question) {
    const chunks = state.data?.articleRag?.chunks || [];
    return chunks
      .map((chunk) => ({ ...chunk, score: scoreQaChunk(question, chunk) }))
      .filter((chunk) => chunk.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, QA_RESULT_LIMIT);
  }

  function configuredRagEndpoint() {
    const fromWindow = window.INVDES_RAG_API_URL || "";
    const fromStorage = (() => {
      try {
        return window.localStorage?.getItem("invdesRagApiUrl") || "";
      } catch {
        return "";
      }
    })();
    const fromMeta = document.querySelector('meta[name="invdes-rag-api-url"]')?.content || "";
    return String(fromWindow || fromStorage || fromMeta).trim();
  }

  async function fetchLiveRagAnswer(question) {
    const endpoint = configuredRagEndpoint();
    if (!endpoint) return null;
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!response.ok) throw new Error("The manuscript answer service is unavailable.");
    return response.json();
  }

  function overviewAnswerChinese(data) {
    const metrics = data.metrics;
    return [
      "这篇文章介绍 InvDesMobility：一个把第一性原理迁移率计算转化为可审计反馈的闭环逆向设计框架。",
      `它从 ${formatNumber(metrics.seedStructures)} 个二维半导体种子结构和 ${formatNumber(metrics.seedChannels)} 个载流子-方向通道出发，通过 reliability gate 保留可进入学习循环的反馈。`,
      `在生成阶段，系统筛选 ${formatCompact(metrics.generatedStructures)} 个结构，提交 ${formatNumber(metrics.deduplicatedSubmittedCandidates)} 个 DFT 候选，最终保留 ${formatNumber(metrics.retainedGeneratedFormulas)} 个生成公式和 ${formatNumber(metrics.trustedGeneratedChannels)} 个可靠通道。`,
    ].join(" ");
  }

  function overviewAnswerEnglish(data) {
    const metrics = data.metrics;
    return [
      "The paper presents InvDesMobility, a closed-loop framework that turns first-principles mobility calculations into auditable feedback for inverse design of two-dimensional semiconductors.",
      `The snapshot starts from ${formatNumber(metrics.seedStructures)} seed structures and ${formatNumber(metrics.seedChannels)} carrier-direction channels, then admits only reliability-gated feedback into the learning loop.`,
      `At campaign scale it screens ${formatCompact(metrics.generatedStructures)} generated structures, submits ${formatNumber(metrics.deduplicatedSubmittedCandidates)} DFT candidates, and retains ${formatNumber(metrics.retainedGeneratedFormulas)} generated formulas with ${formatNumber(metrics.trustedGeneratedChannels)} trusted channels.`,
    ].join(" ");
  }

  function makeQaAnswer(question, matches) {
    const query = asText(question);
    const chinese = hasCjk(question);
    if (/讲了什么|about|overview|summary|paper/.test(query)) {
      return chinese ? overviewAnswerChinese(state.data) : overviewAnswerEnglish(state.data);
    }
    if (/alignn|ranker|acquisition|排序/.test(query)) {
      return chinese
        ? "ALIGNN 在这里是 acquisition ranker：它用于给昂贵的 DFT 验证队列排序，提供富集信号，但不作为最终迁移率标签或最终预测器。最终反馈状态仍由第一性原理验证和可靠性门控决定。"
        : "ALIGNN is used as an acquisition ranker: it prioritizes the expensive DFT validation queue and provides enrichment signal, but it is not treated as the final mobility label or final predictor.";
    }
    if (/reliability|gate|qc|可靠|质量/.test(query)) {
      return chinese
        ? "Reliability gate 的作用是把有限数值输出和可进入学习循环的反馈分开。只有通过工作流完成度、拟合质量、有效质量、带边一致性等检查的载流子-方向通道才会成为 retained feedback。"
        : "The reliability gate separates finite numerical outputs from feedback that is admissible for learning. A carrier-direction channel is retained only after workflow completion, fit quality, effective-mass and band-edge consistency checks.";
    }
    if (/candidate|generated|screen|候选|生成/.test(query)) {
      return chinese
        ? "生成候选先经过去重、结构与电子筛选、形成能筛选、声子稳定性筛选和 post-phonon 几何检查，再由 ALIGNN 排序进入 DFT 验证队列；是否保留仍由第一性原理可靠性门控决定。"
        : "Generated candidates are deduplicated, physically screened, checked for electronic and stability criteria, ranked by ALIGNN, and then sent to DFT validation. Retention is still decided by the first-principles reliability gate.";
    }
    if (!matches.length) {
      return chinese
        ? "没有在当前论文快照中找到足够接近的段落。"
        : "No close passage was found in the current manuscript snapshot.";
    }
    const lead = matches[0].text.split(/(?<=[.!?。！？])\s+/).slice(0, 2).join(" ");
    return chinese ? `最接近的论文段落指向：${lead}` : `The closest manuscript passages point to: ${lead}`;
  }

  function renderQuestionSuggestions(data) {
    const suggestions = data.articleRag?.suggestedQuestions || [];
    $("#question-suggestions").innerHTML = suggestions
      .map((question) => `<button type="button" data-question="${escapeHtml(question)}">${escapeHtml(question)}</button>`)
      .join("");
  }

  function renderQaCitation(chunk) {
    const snippet = chunk.text.length > 460 ? `${chunk.text.slice(0, 457).trim()}...` : chunk.text;
    return `
      <article class="qa-citation">
        <div class="qa-citation-source">${escapeHtml(chunk.source)} / ${escapeHtml(chunk.section)}</div>
        <h3>${escapeHtml(chunk.title)}</h3>
        <p>${escapeHtml(snippet)}</p>
      </article>
    `;
  }

  function renderQaAnswer(answer, citations) {
    $("#manuscript-answer").innerHTML = `
      <div class="qa-answer-main">
        <span class="qa-answer-label">Answer</span>
        <p>${escapeHtml(answer)}</p>
      </div>
      <div class="qa-citations">
        <span class="qa-answer-label">Cited manuscript passages</span>
        ${citations.map(renderQaCitation).join("")}
      </div>
    `;
  }

  function renderQaLoading() {
    $("#manuscript-answer").innerHTML = `
      <div class="qa-answer-main">
        <span class="qa-answer-label">Answer</span>
        <p>Retrieving cited manuscript evidence...</p>
      </div>
    `;
  }

  async function answerManuscriptQuestion(question) {
    const fallback = state.data?.articleRag?.suggestedQuestions?.[0] || "What is this paper about?";
    const normalizedQuestion = question.trim() || fallback;
    $("#manuscript-question").value = normalizedQuestion;

    renderQaLoading();
    try {
      const live = await fetchLiveRagAnswer(normalizedQuestion);
      if (live?.answer) {
        renderQaAnswer(live.answer, live.citations || []);
        return;
      }
    } catch (error) {
      console.warn(error.message || error);
    }

    const matches = getQaMatches(normalizedQuestion);
    renderQaAnswer(makeQaAnswer(normalizedQuestion, matches), matches);
  }

  function renderManuscriptQa(data) {
    renderQuestionSuggestions(data);
    answerManuscriptQuestion(data.articleRag?.suggestedQuestions?.[0] || "");
  }

  function bindManuscriptQa() {
    $("#manuscript-qa-form").addEventListener("submit", (event) => {
      event.preventDefault();
      answerManuscriptQuestion($("#manuscript-question").value);
    });
    $("#question-suggestions").addEventListener("click", (event) => {
      const button = event.target.closest("[data-question]");
      if (!button) return;
      answerManuscriptQuestion(button.dataset.question);
    });
  }

  function renderReliability(data) {
    $("#reliability-grid").innerHTML = data.reliabilityGate
      .map((row) => {
        const total = row.usableOrFiniteChannels + row.failedOrUnusableChannels;
        const retainedWidth = (row.retainedTrustedChannels / total) * 100;
        const withheldWidth = (row.withheldUsableChannels / total) * 100;
        const failedWidth = (row.failedOrUnusableChannels / total) * 100;
        return `
          <article class="reliability-card">
            <h3>${escapeHtml(row.dataset)}</h3>
            <div class="stacked-bar" aria-label="${escapeHtml(row.dataset)} retained ${escapeHtml(percent(row.retainedFraction))}">
              <span class="segment retained" style="width: ${retainedWidth}%"></span>
              <span class="segment withheld" style="width: ${withheldWidth}%"></span>
              <span class="segment failed" style="width: ${failedWidth}%"></span>
            </div>
            <div class="legend">
              <span class="retained">${escapeHtml(formatNumber(row.retainedTrustedChannels))} retained</span>
              <span class="withheld">${escapeHtml(formatNumber(row.withheldUsableChannels))} withheld</span>
              <span class="failed">${escapeHtml(formatNumber(row.failedOrUnusableChannels))} failed or unusable</span>
            </div>
            <div class="alignn-metrics">
              ${miniStat("Usable or finite", formatNumber(row.usableOrFiniteChannels))}
              ${miniStat("Caution", formatNumber(row.cautionChannels))}
              ${miniStat("Weak", formatNumber(row.weakChannels))}
              ${miniStat("Retained fraction", percent(row.retainedFraction))}
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderFigures(data) {
    const figures = data.figures;
    $("#figure-tabs").innerHTML = figures
      .map((figure, index) => {
        return `
          <button class="figure-tab" type="button" role="tab" aria-selected="${index === state.selectedFigure}" data-figure-index="${index}">
            ${escapeHtml(figure.id)}
          </button>
        `;
      })
      .join("");
    document.querySelectorAll("[data-figure-index]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedFigure = Number(button.dataset.figureIndex);
        renderFigures(state.data);
      });
    });
    renderFigurePreview(figures[state.selectedFigure]);
  }

  function renderFigurePreview(figure) {
    if (!figure) {
      $("#figure-preview").innerHTML = `<p>No figure assets were found in the frozen build.</p>`;
      return;
    }
    const assetLabel = figure.kind === "pdf" ? "Open PDF" : "Open asset";
    $("#figure-preview").innerHTML = `
      <h3>${escapeHtml(figure.id)}. ${escapeHtml(figure.title)}</h3>
      <img src="${escapeHtml(figure.previewPath)}" alt="${escapeHtml(figure.title)}">
      <p><a class="text-link" href="${escapeHtml(figure.path)}" target="_blank" rel="noopener">${escapeHtml(assetLabel)}</a></p>
    `;
  }

  function renderDataExplorer(data) {
    $("#trusted-channel-table").innerHTML = makeTable(
      ["Formula", "Channel", "Carrier", `Mobility (${mobilityUnit()})`, "Min fit R²"],
      data.trustedChannels.slice(0, 30).map((row) => [
        row.formula,
        row.channel,
        row.carrier,
        formatMobility(row.mobility),
        formatDecimal(row.minFitR2, 3),
      ])
    );
    $("#round-audit-table").innerHTML = makeTable(
      ["Source step", "Generated", "Submitted", "DFT completed", "Retained formulas", "Trusted channels", "Cumulative labels"],
      data.roundDetails.map((row) => [
        row.roundLabel,
        formatNumber(row.generated),
        formatNumber(row.submitted),
        formatNumber(row.dftCompleted),
        formatNumber(row.retainedFormulas),
        formatNumber(row.trustedChannels),
        formatNumber(row.cumulativeLabels),
      ])
    );
    $("#source-file-list").innerHTML = `
      <ul class="source-list">
        ${data.sourceFiles.map((file) => `<li><code>${escapeHtml(file)}</code></li>`).join("")}
      </ul>
    `;
  }

  function makeTable(headers, rows) {
    return `
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${rows
              .map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`)
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderClaimBoundary(data) {
    $("#supported-claims").innerHTML = data.claimBoundaries.supported
      .map((claim) => `<li>${escapeHtml(claim)}</li>`)
      .join("");
    $("#unsupported-claims").innerHTML = data.claimBoundaries.unsupported
      .map((claim) => `<li>${escapeHtml(claim)}</li>`)
      .join("");
  }

  function renderError(error) {
    const message = escapeHtml(error.message || String(error));
    $("#abstract-text").innerHTML = `<span class="error-box">Failed to load ${DATA_URL}: ${message}</span>`;
  }

  function render(data) {
    state.data = data;
    renderHeader(data);
    renderMetricGrid(data);
    renderFunnel(data);
    renderAlignn(data);
    renderDatabaseSearch(data);
    renderCandidateHighlights(data);
    renderCandidateTable();
    renderReliability(data);
    renderFigures(data);
    renderDataExplorer(data);
    renderClaimBoundary(data);
    renderManuscriptQa(data);
    bindDatabaseControls();
    bindCandidateControls();
    bindManuscriptQa();
  }

  fetch(DATA_URL)
    .then((response) => {
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return response.json();
    })
    .then(render)
    .catch(renderError);
})();
