// ============================================================
// Chart Configuration
// ============================================================

let songTrendChart = null;

const colours = {
    red: "#ff4545",
    redLight: "#ff8585",
    coral: "#ff957d",
    blue: "#60a5fa",
    cyan: "#22d3ee",
    green: "#34d399",
    amber: "#fbbf24",
    pink: "#f472b6",
    grid: "rgba(255, 255, 255, 0.07)",
    text: "#969eae"
};

const chartColours = [
    "#fbbf24", "#60a5fa", "#34d399", "#f472b6", "#ff4545",
    "#60a5fa", "#fb7185", "#a3e635", "#c084fc", "#2dd4bf"
];

Chart.defaults.color = colours.text;
Chart.defaults.font.family = "Inter, system-ui, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.responsive = true;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.animation.duration = 650;

Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyle = "circle";
Chart.defaults.plugins.legend.labels.boxWidth = 8;
Chart.defaults.plugins.legend.labels.boxHeight = 8;
Chart.defaults.plugins.legend.labels.padding = 18;

Chart.defaults.plugins.tooltip.backgroundColor = "#1d2430";
Chart.defaults.plugins.tooltip.titleColor = "#f6f7fb";
Chart.defaults.plugins.tooltip.bodyColor = "#d7dbe4";
Chart.defaults.plugins.tooltip.padding = 12;
Chart.defaults.plugins.tooltip.cornerRadius = 10;


// ============================================================
// Formatting and Chart Scales
// ============================================================

function formatDateLabel(value) {
    const date = new Date(String(value).split("/")[0] + "T00:00:00");

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleDateString("en-IE", {
        day: "numeric",
        month: "short",
        year: "2-digit"
    });
}
function standardScales(xTitle, yTitle) {
    return {
        x: {
            grid: {
                display: false
            },
            border: {
                display: false
            },
            title: {
                display: true,
                text: xTitle,
                color: colours.text,
                padding: 12
            },
            ticks: {
                color: colours.text,
                maxRotation: 0,
                autoSkip: true,
                maxTicksLimit: 10
            }
        },

        y: {
            beginAtZero: true,
            grid: {
                color: colours.grid
            },
            border: {
                display: false
            },
            title: {
                display: true,
                text: yTitle,
                color: colours.text,
                padding: 12
            },
            ticks: {
                color: colours.text,
                precision: 0
            }
        }
    };
}
function dateScales(xTitle, yTitle) {
    const scales = standardScales(xTitle, yTitle);
    scales.x.ticks.callback = function(value) {
        return formatDateLabel(this.getLabelForValue(value));
    };
    return scales;
}

function horizontalBarScales(xTitle) {
    return {
        x: {
            beginAtZero: true,
            grid: {
                color: colours.grid
            },
            border: {
                display: false
            },
            title: {
                display: true,
                text: xTitle,
                color: colours.text,
                padding: 12
            },
            ticks: {
                precision: 0
            }
        },

        y: {
            grid: {
                display: false
            },
            border: {
                display: false
            },
            ticks: {
                autoSkip: false,
                callback: function(value) {
                    const label = this.getLabelForValue(value);

                    return label.length > 28
                        ? label.slice(0, 28) + "…"
                        : label;
                }
            }
        }
    };
}


// Measure rendered text rather than character counts because mixed scripts
// and variable-width letters need different space in the song labels.
function wrapSongLabel(context, label, width) {
    const characters = Array.from(label);
    const lines = [];
    let line = "";
    for (const character of characters) {
        if (line && context.measureText(line + character).width > width) {
            const breakAt = line.lastIndexOf(" ");
            const wrapAtWord = breakAt > 0 && context.measureText(line.slice(0, breakAt)).width > width * 0.55;
            lines.push((wrapAtWord ? line.slice(0, breakAt) : line).trim());
            line = wrapAtWord ? line.slice(breakAt + 1) : "";
            if (lines.length === 2) {
                let lastLine = lines[1];
                while (lastLine && context.measureText(lastLine + "…").width > width) {
                    lastLine = Array.from(lastLine).slice(0, -1).join("");
                }
                lines[1] = lastLine + "…";
                return lines;
            }
        }
        line += character;
    }
    if (line.trim()) {
        lines.push(line.trim());
    }
    return lines;
}

function topSongScales() {
    const scales = horizontalBarScales("Plays");
    scales.y.afterFit = scale => { scale.width = Math.round(scale.chart.width * 0.52); };
    scales.y.ticks = {
        autoSkip: false,
        font: {size: 13, lineHeight: 1.2},
        padding: 10,
        callback: function(value) {
            const label = this.getLabelForValue(value);
            const context = this.chart.ctx;
            const width = Math.max(70, this.chart.width * 0.52 - 24);
            context.save();
            context.font = "13px Inter, system-ui, sans-serif";
            try {
                return wrapSongLabel(context, label, width);
            } finally {
                context.restore();
            }
        }
    };
    return scales;
}

function formatDuration(seconds) {
    const minutes = Math.floor(Number(seconds) / 60);
    return Math.floor(minutes / 60).toLocaleString() + "h " + (minutes % 60) + "m";
}
function formatWeekRange(week) {
    return String(week).split("/").map(formatDateLabel).join(" – ");
}
// ============================================================
// API Requests
// ============================================================

const LOCAL_API_ORIGIN = "http://127.0.0.1:8000";
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const IMPORT_POLL_INTERVAL_MS = 1500;
const WEEK_PAGE_SIZE = 12;
const API_BASE = (location.pathname.startsWith("/dashboard") || location.port === "8000") ? location.origin : LOCAL_API_ORIGIN;
const activeDataset = sessionStorage.getItem("musicDataset");
async function fetchData(url) {
    url = API_BASE + url;
    const response = await fetch(url, {headers: activeDataset ? {"X-Dataset-Token": activeDataset} : {}});
    if (!response.ok) throw new Error("Request failed: " + response.status);
    return response.json();
}
// ============================================================
// Dashboard Data and Charts
// ============================================================

async function loadListeningTime() {
    const data = await fetchData("/api/listening-time");
    document.getElementById("listening_time").textContent = formatDuration(data.total_seconds);
    document.getElementById("listening_time").title = data.formatted_time;
}
async function loadSessions() {
    const data = await fetchData("/api/sessions");
    document.getElementById("total_sessions").textContent = data.total_sessions.toLocaleString();
}

async function loadSummary() {
    const data = await fetchData(
        "/api/summary"
    );


    document.getElementById("music_plays").textContent =
        data.music_plays;

    document.getElementById("unique_videos").textContent =
        data.unique_videos;

    document.getElementById("unique_channels").textContent =
        data.unique_channels;
}


async function loadTopSongs() {
    const data = await fetchData(
        "/api/top-songs"
    );

    const songTitles = data.map(item => item.title);
    const plays = data.map(item => item.plays);


    new Chart(
        document.getElementById("top_songs"),
        {
            type: "bar",

            data: {
                labels: songTitles,
                datasets: [
                    {
                        label: "Times listened",
                        data: plays,
                        backgroundColor: colours.red,
                        borderRadius: 7,
                        borderSkipped: false,
                        barPercentage: 0.72
                    }
                ]
            },

            options: {
                indexAxis: "y",
                scales: topSongScales(),
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        }
    );
}
async function loadTopChannels() {
    const data = await fetchData(
        "/api/top-channels"
    );

    const channelNames = data.map(item => item.channel);
    const plays = data.map(item => item.plays);

    new Chart(
        document.getElementById("top_channels_chart"),
        {
            type: "bar",

            data: {
                labels: channelNames,
                datasets: [
                    {
                        label: "Plays",
                        data: plays,
                        backgroundColor: colours.coral,
                        borderRadius: 7,
                        borderSkipped: false,
                        barPercentage: 0.72
                    }
                ]
            },

            options: {
                indexAxis: "y",
                scales: horizontalBarScales("Plays"),
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        }
    );
}

async function loadSessionHighlights() {
    const data = await fetchData(
        "/api/session-highlights"
    );

    for (const key of ["largest_session", "longest_session"]) {
        const session = data[key];
        const favourites = Object.entries(session?.top_songs ?? {});
        const mostPlays = Math.max(0, ...favourites.map(([, plays]) => plays));
        const leaders = favourites.filter(([, plays]) => plays === mostPlays).map(([title]) => title);
        document.getElementById(key + "_favourite").textContent = mostPlays > 1
            ? "On repeat: " + leaders.join(" / ") + " · " + mostPlays + " plays each" : "A session of variety — no song played twice.";
    }
    if (!data.largest_session || !data.longest_session) {
        for (const key of ["largest_session", "longest_session"]) {
            document.getElementById(key + "_events").textContent = "0";
            document.getElementById(key + "_date").textContent = "—";
            document.getElementById(key + "_duration").textContent = "0h 0m";
            document.getElementById(key + "_favourite").textContent = "No listening sessions";
        }
        return;
    }
    const largest = data.largest_session;
    const longest = data.longest_session;

    document.getElementById("largest_session_events").textContent =
        largest.events;

    document.getElementById("largest_session_date").textContent =
        formatDateLabel(largest.date);

    document.getElementById("largest_session_duration").textContent =
        formatDuration(largest.listening_seconds);

    document.getElementById("longest_session_events").textContent =
        longest.events;

    document.getElementById("longest_session_date").textContent =
        formatDateLabel(longest.date);

    document.getElementById("longest_session_duration").textContent =
        formatDuration(longest.listening_seconds);
}

async function loadListeningByDate() {
    const data = await fetchData(
        "/api/listening-by-date"
    );

    const dates = data.map(item => item.date);
    const plays = data.map(item => item.plays);

    new Chart(
        document.getElementById("listening_timeline"),
        {
            type: "line",

            data: {
                labels: dates,
                datasets: [
                    {
                        label: "Music Plays",
                        data: plays,
                        borderColor: colours.blue,
                        backgroundColor: "rgba(96, 165, 250, 0.14)",
                        fill: true,
                        tension: 0.3,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        borderWidth: 2
                    }
                ]
            },

            options: {
                scales: dateScales("Date", "Plays"),

                plugins: {
                    legend: {
                        position: "bottom",
                        align: "start"
                    }
                },

                interaction: {
                    mode: "index",
                    intersect: false
                }
            }
        }
    );
}
async function loadListeningByHour() {
    const data = await fetchData(
        "/api/listening-by-hour"
    );

    const hours = Array.from({length: 24}, (_, hour) => String(hour).padStart(2, "0") + ":00");
    const plays = hours.map((_, hour) => data.find(item => item.hour === hour)?.plays ?? 0);

    new Chart(
        document.getElementById("hour_chart"),
        {
            type: "bar",

            data: {
                labels: hours,
                datasets: [
                    {
                        label: "Music plays",
                        data: plays,
                        backgroundColor: colours.blue,
                        borderRadius: 7,
                        borderSkipped: false
                    }
                ]
            },

            options: {
                scales: standardScales(
                    "Hour of day (24-hour clock)",
                    "Music plays"
                ),

                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        }
    );
}
async function loadListeningByWeekday() {
    const data = await fetchData(
        "/api/listening-by-weekday"
    );

    const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    const plays = weekdays.map(day => data.find(item => item.weekday === day)?.plays ?? 0);

    new Chart(
        document.getElementById("weekday_chart"),
        {
            type: "bar",

            data: {
                labels: weekdays,
                datasets: [
                    {
                        label: "Music plays",
                        data: plays,
                        backgroundColor: colours.cyan,
                        borderRadius: 7,
                        borderSkipped: false
                    }
                ]
            },

            options: {
                scales: {
                    ...standardScales("Weekday", "Music plays"),
                    x: {...standardScales("Weekday", "Music plays").x,
                        ticks: {autoSkip: false, maxRotation: 0, font: {size: 11},
                            callback: function(value) { return this.getLabelForValue(value).slice(0, 3); }}
                    }
                },

                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        }
    );
}
function renderWeeklyWinners(visible, leaders) {
    const body = document.getElementById("weekly_winners");
    body.replaceChildren();
    visible.forEach((item, index) => {
        const row = document.createElement("tr");
        [formatWeekRange(item.week), leaders[index].title, leaders[index].plays].forEach((value, column) => {
            const cell = document.createElement("td");
            cell.textContent = value;
            if (column === 1 && leaders[index].titles.length > 1) {
                cell.replaceChildren();
                const details = document.createElement("details");
                const summary = document.createElement("summary");
                const others = leaders[index].titles.length - 1;
                summary.textContent = leaders[index].title + " + " + others + (others === 1 ? " joint winner" : " joint winners");
                details.appendChild(summary);
                const list = document.createElement("ul");
                leaders[index].titles.forEach(title => {
                    const entry = document.createElement("li");
                    entry.textContent = title;
                    list.appendChild(entry);
                });
                details.appendChild(list);
                cell.appendChild(details);
            }
            row.appendChild(cell);
        });
        body.appendChild(row);
    });
}

async function loadListeningByWeek() {
    const data = (await fetchData("/api/listening-by-week?limit=10000"))
        .sort((first, second) => first.week.localeCompare(second.week));
    const pageSize = WEEK_PAGE_SIZE;
    let start = Math.max(0, data.length - pageSize);
    let chart;
    function render() {
        const visible = data.slice(start, start + pageSize);
        const leaders = visible.map(item => {
            const max = Math.max(0, ...item.songs.map(song => song.plays));
            const titles = item.songs.filter(song => song.plays === max).map(song => song.title);
            return {plays: max, titles, title: titles[0] || "No plays"};
        });
        document.getElementById("weeks_range").textContent = visible.length
            ? formatDateLabel(visible[0].week) + " – " + formatDateLabel(visible.at(-1).week.split("/").at(-1)) : "No weekly history";
        document.getElementById("weeks_previous").disabled = start === 0;
        document.getElementById("weeks_next").disabled = start + pageSize >= data.length;
        renderWeeklyWinners(visible, leaders);
        document.getElementById("weekly_songs_chart").parentElement.style.minWidth = Math.max(320, visible.length * 76 + 65) + "px";
        if (chart) chart.destroy();
        chart = new Chart(document.getElementById("weekly_songs_chart"), {
            type: "bar",
            data: {labels: visible.map(item => item.week), datasets: [{label: "Winning song plays", data: leaders.map(item => item.plays), backgroundColor: colours.red, borderRadius: 6}]},
            options: {
                scales: {...standardScales("Week starting", "Plays"), x: {...standardScales("Week starting", "Plays").x,
                    ticks: {maxRotation: 0, autoSkip: false, font: {size: 11}, callback: function(value) { return formatDateLabel(this.getLabelForValue(value)); }}}},
                plugins: {legend: {display: false}, tooltip: {callbacks: {
                    title: items => formatWeekRange(items[0].label),
                    label: context => leaders[context.dataIndex].title + ": " + context.formattedValue + " plays",
                    afterLabel: context => leaders[context.dataIndex].titles.length > 1 ? "Joint winners — expand the table row below" : ""
                }}}
            }
        });
    }
    document.getElementById("weeks_previous").addEventListener("click", () => { start = Math.max(0, start - pageSize); render(); });
    document.getElementById("weeks_next").addEventListener("click", () => { start = Math.min(data.length - 1, start + pageSize); render(); });
    render();
}

async function loadSongConcentration() {
    const data = await fetchData(
        "/api/song-concentration"
    );

    const topN = data.map(item => "Top " + item.top_n);
    const percentages = data.map(item => item.percentage);

    new Chart(
        document.getElementById("concentration_chart"),
        {
            type: "bar",

            data: {
                labels: topN,
                datasets: [
                    {
                        label: "Percentage of Plays",
                        data: percentages,
                        backgroundColor: colours.green,
                        borderRadius: 7,
                        borderSkipped: false
                    }
                ]
            },

            options: {
                scales: standardScales(
                    "Song group",
                    "Percentage of plays"
                ),

                plugins: {
                    legend: {
                        display: false
                    },

                    tooltip: {
                        callbacks: {
                            label: context =>
                                context.formattedValue + "% of plays"
                        }
                    }
                }
            }
        }
    );
}
async function loadLoyalty() {
    const data = await fetchData(
        "/api/loyalty"
    );

    document.getElementById("repeat_percentage").textContent =
        data.repeat_play_percentage.toFixed(1) + "%";

    document.getElementById("one_time_songs").textContent =
        data.one_time_songs;

    document.getElementById("repeated_songs").textContent =
        data.repeated_songs;

    document.getElementById("repeat_plays").textContent =
        data.repeat_plays;
}
async function loadPersistentSongs() {
    const data = await fetchData(
        "/api/persistent-songs"
    );

    const songTitles = data.map(item => item.title);
    const weeks = data.map(item => item.weeks);


    new Chart(
        document.getElementById("persistent_songs_chart"),
        {
            type: "bar",

            data: {
                labels: songTitles,
                datasets: [
                    {
                        label: "Weeks listened",
                        data: weeks,
                        backgroundColor: colours.green,
                        borderRadius: 7,
                        borderSkipped: false,
                        barPercentage: 0.72
                    }
                ]
            },

            options: {
                indexAxis: "y",
                scales: horizontalBarScales("Weeks present"),

                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        }
    );
}
function createSongRankingsChart(weeks, datasets) {
    return new Chart(
        document.getElementById("song_rankings_chart"),
        {
            type: "line",

            data: {
                labels: weeks,
                datasets: datasets
            },

            options: {
                interaction: {
                    mode: "nearest",
                    intersect: false
                },

                plugins: {
                    legend: {
                        display: true,
                        position: "bottom",
                        align: "start",

                        labels: {
                            padding: 15,

                            generateLabels: function(chart) {
                                return Chart.defaults
                                    .plugins
                                    .legend
                                    .labels
                                    .generateLabels(chart)
                                    .map(label => ({
                                        ...label,

                                        text: label.text.length > 34
                                            ? label.text.slice(0, 34) + "…"
                                            : label.text
                                    }));
                            }
                        }
                    },

                    tooltip: {
                        callbacks: {
                            title: items =>
                                "Week of "
                                + formatDateLabel(items[0].label),

                            label: context =>
                                context.dataset.label
                                + ": rank "
                                + context.formattedValue
                        }
                    }
                },

                scales: {
                    x: {
                        grid: {
                            display: false
                        },

                        border: {
                            display: false
                        },

                        title: {
                            display: true,
                            text: "Week starting",
                            color: colours.text,
                            padding: 12
                        },

                        ticks: {
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 6,

                            callback: function(value) {
                                return formatDateLabel(
                                    this.getLabelForValue(value)
                                );
                            }
                        }
                    },

                    y: {
                        reverse: true,
                        min: 1,
                        offset: true,
                        beginAtZero: false,

                        grid: {
                            color: colours.grid
                        },

                        border: {
                            display: false
                        },

                        title: {
                            display: true,
                            text: "Chart rank",
                            color: colours.text,
                            padding: 12
                        },

                        ticks: {
                            stepSize: 1,
                            precision: 0
                        }
                    }
                }
            }
        }
    );
}

async function loadSongRankings() {
    const data = await fetchData(
        "/api/song-rankings-by-week"
    );

    // Include missing calendar weeks so the chart shows gaps instead of
    // connecting observations that were separated by weeks with no plays.
    const weeks = [...new Set(data.map(item => item.week))].sort();
    if (weeks.length) {
        const first = new Date(weeks[0].split("/")[0] + "T00:00:00Z");
        const last = new Date(weeks.at(-1).split("/")[0] + "T00:00:00Z");
        weeks.length = 0;
        for (let date = first; date <= last; date.setUTCDate(date.getUTCDate() + 7)) {
            const end = new Date(date);
            end.setUTCDate(end.getUTCDate() + 6);
            weeks.push(date.toISOString().slice(0, 10) + "/" + end.toISOString().slice(0, 10));
        }
    }

    const songs = [
        ...new Set(
            data.map(item => item.title)
        )
    ];

    const datasets = songs.map((song, index) => {
        const rankings = weeks.map(week => {
            const result = data.find(
                item =>
                    item.week === week
                    && item.title === song
            );

            // An absent rank is a gap, not zero: rank 1 is already the best
            // possible position, so zero would imply a misleading result.
            return result ? result.rank : null;
        });

        return {
            label: song,
            data: rankings,
            spanGaps: false,
            hidden: false,
            borderColor:
                chartColours[index % chartColours.length],
            backgroundColor:
                chartColours[index % chartColours.length],
            borderWidth: 2,
            pointRadius: 2.5,
            pointHoverRadius: 6,
            tension: 0
        };
    });

    const rankingChart = createSongRankingsChart(weeks, datasets);
    const selector = document.getElementById("ranking_selector");
    songs.forEach((song, index) => {
        const option = document.createElement("option");
        option.value = index;
        option.textContent = song;
        selector.appendChild(option);
    });
    const all = document.createElement("option");
    all.value = "all";
    all.textContent = "Compare all five songs";
    selector.prepend(all);
    selector.value = "all";
    selector.addEventListener("change", () => {
        rankingChart.data.datasets.forEach((_, index) => rankingChart.setDatasetVisibility(index, selector.value === "all" || index === Number(selector.value)));
        rankingChart.options.plugins.legend.display = selector.value === "all";
        rankingChart.update();
    });
}

async function loadSongSelector() {
    const data = await fetchData(
        "/api/top-songs"
    );

    const selector =
        document.getElementById("song_selector");

    data.forEach(song => {
        const option =
            document.createElement("option");

        option.value = song.title;
        option.textContent = song.title;

        selector.appendChild(option);
    });

    selector.addEventListener("change", function() {
        const selectedSong = selector.value;

        if (selectedSong !== "") {
            loadSongTrend(selectedSong);
        }
    });

    if (data.length > 0) {
        selector.value = data[0].title;
        await loadSongTrend(data[0].title);
    }
}
async function loadSongTrend(title) {
    const data = await fetchData(
        "/api/song-trend?title="
        + encodeURIComponent(title)
    );

    const weeks =
        data.trend_data.map(item => item.week);

    const plays =
        data.trend_data.map(item => item.plays);

    if (songTrendChart !== null) {
        songTrendChart.destroy();
    }

    songTrendChart = new Chart(
        document.getElementById("song_trend_chart"),
        {
            type: "line",

            data: {
                labels: weeks,

                datasets: [
                    {
                        label: data.title,
                        data: plays,
                        borderColor: colours.amber,
                        backgroundColor:
                            "rgba(251, 191, 36, 0.12)",
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointHoverRadius: 6,
                        borderWidth: 2
                    }
                ]
            },

            options: {
                scales: dateScales("Week", "Plays"),

                plugins: {
                    legend: {
                        position: "bottom",
                        align: "start"
                    }
                },

                interaction: {
                    mode: "index",
                    intersect: false
                }
            }
        }
    );
}


// ============================================================
// Dashboard Initialisation
// ============================================================

const loaders = [loadSummary, loadListeningTime, loadSessions, loadTopSongs, loadTopChannels,
    loadListeningByDate, loadListeningByHour, loadListeningByWeekday, loadListeningByWeek,
    loadSessionHighlights, loadSongConcentration, loadLoyalty, loadPersistentSongs, loadSongRankings, loadSongSelector];
// Independent panels can still render when one endpoint fails; collect
// failures afterwards so partial data is accompanied by a visible warning.
Promise.allSettled(loaders.map(load => load())).then(results => {
    const failed = results.filter(result => result.status === "rejected");
    if (failed.length) {
        const status = document.getElementById("load_status");
        status.hidden = false;
        status.textContent = "Some listening data could not load. Check that the API is running at 127.0.0.1:8000, then refresh.";
        failed.forEach(result => console.error(result.reason));
    }
});


// ============================================================
// History Imports
// ============================================================

// Reload on dataset changes so in-flight requests cannot mix reports.
document.getElementById("export_timezone").value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
const importStatus = document.getElementById("import_status");
const importButton = document.getElementById("import_button");
const originalButton = document.getElementById("original_report");
const deleteButton = document.getElementById("delete_import");
let savedImport = sessionStorage.getItem("lastMusicImport");
originalButton.hidden = !activeDataset;
deleteButton.hidden = !savedImport;
document.getElementById("dataset_label").textContent = activeDataset ? "Showing your imported report (UTC)" : "Showing the original report";
importStatus.textContent = sessionStorage.getItem("musicImportSummary") || "";

async function importRequest(path, options = {}) {
    const response = await fetch(API_BASE + path, options);
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Request failed (" + response.status + ")");
    return body;
}

// Poll the job token rather than the active report token, since the
// previous report remains selected until the new import completes.
async function monitorImport(token) {
    importButton.disabled = true;
    deleteButton.disabled = true;
    try {
        while (true) {
            const job = await importRequest("/api/imports/current", {headers: {"X-Dataset-Token": token}});
            importStatus.textContent = job.message;
            if (job.status === "failed") {
                sessionStorage.removeItem("pendingMusicImport");
                throw new Error(job.message);
            }
            if (job.status === "complete") {
                const summary = job.summary;
                sessionStorage.setItem("musicImportSummary", summary.music_plays + " music plays from " + summary.watch_events + " usable watch events. " + summary.excluded_shorts + " Shorts excluded; " + summary.unverified_videos + " videos left out because their format could not be verified. " + summary.skipped_records + " records skipped because of invalid dates or URLs.");
                sessionStorage.setItem("musicDataset", token);
                sessionStorage.removeItem("pendingMusicImport");
                location.reload();
                return;
            }
            await new Promise(resolve => setTimeout(resolve, IMPORT_POLL_INTERVAL_MS));
        }
    } catch (error) {
        importStatus.textContent = error.message + " Refresh to reconnect, or try another import.";
    } finally {
        importButton.disabled = false;
        deleteButton.disabled = false;
    }
}

document.getElementById("import_form").addEventListener("submit", async event => {
    event.preventDefault();
    const file = document.getElementById("history_file").files[0];
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
        importStatus.textContent = "Choose a history file smaller than 25 MB.";
        return;
    }
    if (savedImport) {
        importStatus.textContent = "Delete your previous import before importing another file.";
        return;
    }
    importButton.disabled = true;
    importStatus.textContent = "Uploading history…";
    try {
        const created = await importRequest("/api/imports?filename=" + encodeURIComponent(file.name) + "&timezone=" + encodeURIComponent(document.getElementById("export_timezone").value), {method: "POST", body: file, headers: {"Content-Type": "application/octet-stream"}});
        savedImport = created.dataset_token;
        sessionStorage.setItem("lastMusicImport", savedImport);
        sessionStorage.setItem("pendingMusicImport", savedImport);
        deleteButton.hidden = false;
        await monitorImport(savedImport);
    } catch (error) {
        importStatus.textContent = error.message;
    } finally {
        importButton.disabled = false;
    }
});
originalButton.addEventListener("click", () => {
    sessionStorage.removeItem("musicDataset");
    location.reload();
});
deleteButton.addEventListener("click", async () => {
    try {
        await importRequest("/api/imports/current", {method: "DELETE", headers: {"X-Dataset-Token": savedImport}});
        for (const key of ["musicDataset", "lastMusicImport", "pendingMusicImport", "musicImportSummary"]) sessionStorage.removeItem(key);
        location.reload();
    } catch (error) {
        importStatus.textContent = error.message;
    }
});
const pendingImport = sessionStorage.getItem("pendingMusicImport");
if (pendingImport) monitorImport(pendingImport);
