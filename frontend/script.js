async function loadSummary() {
    const response = await fetch("http://127.0.0.1:8000/api/summary");

    const data = await response.json();

    console.log(data);

    document.getElementById("music_plays").textContent = data.music_plays;
    document.getElementById("unique_videos").textContent = data.unique_videos;
    document.getElementById("unique_channels").textContent = data.unique_channels
}

async function loadTopSongs(){
    const response = await fetch("http://127.0.0.1:8000/api/top-songs");
    const data = await response.json();

    const title = data.map(item => item.title)
    const plays = data.map(item => item.plays)

    console.log("Testing loadTopSongs()")
    console.log(title)
    console.log(plays)

    const chart = new Chart(
        document.getElementById("top_songs"),
        {
            type: "bar",
            data: {
                labels: title,
                datasets: [{
                    label: "Times listened",
                    data: plays
                }]
            },
            options: {
                indexAxis: 'y'
            }
        }
    )
}
async function loadTopChannels(){
    const response = await fetch("http://127.0.0.1:8000/api/top-channels");
    const data = await response.json();

    const titles = data.map(item => item.channel)
    const plays = data.map(item => item.plays)

    new Chart(
    document.getElementById("top_channels_chart"),
    {
        type: "bar",

        data: {
            labels: titles,

            datasets: [
                {
                    label: "Plays",
                    data: plays
                }
            ]
        },

        options: {
            indexAxis: "y"
        }
    }
);


}


async function loadListeningByDate(){
    const response = await fetch("http://127.0.0.1:8000/api/listening-by-date");
    const data = await response.json();

    const dates = data.map(item => item.date)
    const plays = data.map(item => item.plays)

    //console.log(dates)
    //console.log(plays)

    const chart = new Chart(
    document.getElementById("listening_timeline"),
    {
        type: "line",
        data: {
            labels: dates,
            datasets: [{
                label: "Music Videos Played",
                data: plays
            }]
        }
    }
)
}
async function loadListeningByHour(){
    const response = await fetch("http://127.0.0.1:8000/api/listening-by-hour");
    const data = await response.json();

    const hours = data.map(item => item.hour)
    const plays = data.map(item => item.plays)

    const chart = new Chart(
    document.getElementById("hour_chart"),
    {
        type: "bar",
        data: {
            labels: hours,
            datasets: [{
                label: "Number of songs listened to",
                data: plays
            }]
        }
    }
)

}
async function loadListeningByWeekday(){
    const response = await fetch("http://127.0.0.1:8000/api/listening-by-weekday");
    const data = await response.json();

    const weekdays = data.map(item => item.weekday)
    const plays = data.map(item => item.plays)

    const chart = new Chart(
    document.getElementById("weekday_chart"),
    {
        type: "bar",
        data: {
            labels: weekdays,
            datasets: [{
                label: "Number of songs listened to",
                data: plays
            }]
        }
    }
)

}
async function loadListeningByWeek() {
    const response = await fetch(
        "http://127.0.0.1:8000/api/listening-by-week"
    );

    const data = await response.json();

    const weeks = [];
    const topSongTitles = [];
    const topSongPlays = [];

    data.forEach(week => {
        weeks.push(week.week);

        if (week.songs.length > 0) {
            topSongTitles.push(week.songs[0].title);
            topSongPlays.push(week.songs[0].plays);
        }
    });

    console.log("Testing loadListeningByWeek()");
    console.log(weeks);
    console.log(topSongTitles);
    console.log(topSongPlays);

    new Chart(
        document.getElementById("weekly_songs_chart"),
        {
            type: "bar",

            data: {
                labels: weeks,
                datasets: [
                    {
                        label: "Top Song Plays",
                        data: topSongPlays
                    }
                ]
            }
        }
    );
}
async function loadSessionHighlights() {
    const response = await fetch(
        "http://127.0.0.1:8000/api/session-highlights"
    );

    const data = await response.json();

    const largest = data.largest_session;
    const longest = data.longest_session;


    document.getElementById("largest_session_events").textContent =
        largest.events;

    document.getElementById("largest_session_date").textContent =
        largest.date;

    document.getElementById("largest_session_duration").textContent =
        largest.formatted_listening_time;


    document.getElementById("longest_session_events").textContent =
        longest.events;

    document.getElementById("longest_session_date").textContent =
        longest.date;

    document.getElementById("longest_session_duration").textContent =
        longest.formatted_listening_time;
}

async function loadSongConcentration() {
    const response = await fetch(
        "http://127.0.0.1:8000/api/song-concentration"
    );

    const data = await response.json();

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
                        data: percentages
                    }
                ]
            }
        }
    );
}
async function loadLoyalty() {
    const response = await fetch("http://127.0.0.1:8000/api/loyalty");
    const data = await response.json();

    document.getElementById("repeat_percentage").textContent =
        data.repeat_play_percentage.toFixed(1) + "%";
    document.getElementById("one_time_songs").textContent =
    data.one_time_songs;

    document.getElementById("repeated_songs").textContent =
        data.repeated_songs;

    document.getElementById("repeat_plays").textContent =
        data.repeat_plays;
}
async function loadPersistentSongs(){
    const response = await fetch("http://127.0.0.1:8000/api/persistent-songs");
    const data = await response.json();

    const title = data.map(item => item.title)
    const weeks = data.map(item => item.weeks)

    console.log("Testing loadTopSongs()")
    console.log(title)
    console.log(weeks)

    const chart = new Chart(
        document.getElementById("persistent_songs_chart"),
        {
            type: "bar",
            data: {
                labels: title,
                datasets: [{
                    label: "Weeks listened",
                    data: weeks
                }]
            },
            options: {
                indexAxis: 'y'
            }
        }
    )
}


loadSummary()

loadTopSongs()
loadTopChannels()


loadListeningByDate()
loadListeningByHour()
loadListeningByWeekday()
loadListeningByWeek()

loadSessionHighlights()

loadSongConcentration()
loadLoyalty()
loadPersistentSongs()
