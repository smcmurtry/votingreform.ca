create_dropdown('#election-dropdown', elections);
create_dropdown('#voting-system-dropdown', voting_systems);
create_dropdown('#region-dropdown', regions);

function size_nav() {
  var dropdown_h = +d3.select('#nav-inner').style('height').slice(0, -2);
  d3.select('#nav').style('height', (dropdown_h+15) + 'px');
  d3.select('#top-content').style('margin-top', (dropdown_h+15) + 'px');
}
size_nav();
window.addEventListener('resize', size_nav, false);

// 2015 has simulated results for every voting system; later elections only
// have the actual (First Past the Post) results.
var q = d3.queue()
  .defer(d3.json, './data/elections_summary.json')
  .defer(d3.json, './data/tot_summary.json')
  .defer(d3.csv, './data/pct_summary.csv', bars.type)
  .defer(d3.csv, './data/fptp_clean.csv', blocks.type)
  .defer(d3.csv, './data/dmp_clean.csv', blocks.type)
  .defer(d3.csv, './data/mmp_clean.csv', blocks.type)
  .defer(d3.csv, './data/irv_clean.csv', blocks.type)
  .defer(d3.csv, './data/stv_clean.csv', blocks.type);

var other_years = elections
  .map(function(d) { return d.abbr; })
  .filter(function(year) { return year != sim_year; });

other_years.forEach(function(year) {
  q.defer(d3.json, './data/' + year + '/tot_summary.json')
    .defer(d3.csv, './data/' + year + '/pct_summary.csv', bars.type)
    .defer(d3.csv, './data/' + year + '/fptp_clean.csv', blocks.type);
});

q.awaitAll(function(error, files) {
  if (error) { throw error; }

  var summary = files[0];

  // store[year] = {tot: seats by region/system, pct: share rows, dataz: seat rows}
  var store = {};
  store[sim_year] = {
    tot: files[1],
    pct: files[2],
    dataz: blocks.prep({FPTP: files[3], DMP: files[4], MMP: files[5], IRV: files[6], STV: files[7]})
  };
  other_years.forEach(function(year, i) {
    var offset = 8 + 3*i;
    store[year] = {
      tot: files[offset],
      pct: files[offset+1],
      dataz: blocks.prep({FPTP: files[offset+2]})
    };
  });

  page_w = +d3.select('#main').style('width').slice(0,-2);
  table.init();
  bars.init();
  blocks.init();
  draw_summary(summary);

  d3.select('#election-dropdown').on('change', function() {
    // Simulations only exist for one election, so fall back to the real results.
    if (get_selected_row('#election-dropdown', elections) != sim_year) {
      set_selected_row('#voting-system-dropdown', voting_systems, 'FPTP');
    }
    update_all();
  });
  d3.select('#voting-system-dropdown').on('change', function() {
    if (get_selected_row('#voting-system-dropdown', voting_systems) != 'FPTP') {
      set_selected_row('#election-dropdown', elections, sim_year);
    }
    update_all();
  });
  d3.select('#region-dropdown').on('change', update_all);

  update_all();

  function update_all() {

    var sel_year = get_selected_row('#election-dropdown', elections);
    var sel_system = get_selected_row('#voting-system-dropdown', voting_systems);
    var sel_region = get_selected_row('#region-dropdown', regions);
    var sel_system_label = voting_systems.filter(function(d) { return d.abbr == sel_system; })[0].label;
    var sel_region_label = regions.filter(function(d) { return d.abbr == sel_region; })[0].label;

    d3.select('#system-title').text(sel_system_label);
    d3.selectAll('.region-name').text(sel_region_label);
    d3.selectAll('.year-label').text(sel_year);
    d3.select('#sim-note').style('display', (sel_year == sim_year) ? 'none' : 'block');
    d3.selectAll('#summary-table tbody tr').classed('selected', function(d) { return d.year == sel_year; });

    table.update(store[sel_year].tot, sel_system, sel_region);
    bars.update(store[sel_year].pct, sel_system, sel_region);
    blocks.update(store[sel_year].dataz, sel_system, sel_region);
  }

});

// Table comparing, for each election, the leading party's share of the vote
// with its share of the seats.
function draw_summary(summary) {

  var pct = function(v) { return d3.format('.1f')(100*v) + '%'; };
  var top_party = function(obj) {
    return parties.slice().sort(function(a, b) { return obj[b] - obj[a]; })[0];
  };

  var rows = elections.map(function(e) {
    var s = summary[e.abbr];
    var seat_winner = top_party(s.seats);
    var vote_winner = top_party(s.vote_share);
    return {
      year: e.abbr,
      seat_winner: seat_winner,
      vote_winner: vote_winner,
      vote_share: s.vote_share[seat_winner],
      seat_share: s.seats[seat_winner]/s.total_seats,
      majority: s.seats[seat_winner] > s.total_seats/2
    };
  });

  var tr = d3.select('#summary-table tbody').selectAll('tr')
    .data(rows)
    .enter()
    .append('tr')
    .classed('mismatch', function(d) { return d.seat_winner != d.vote_winner; });

  tr.append('th').attr('scope', 'row').text(function(d) { return d.year; });
  tr.append('td').text(function(d) {
    return party_labels[d.seat_winner] + (d.majority ? ' (majority)' : ' (minority)');
  });
  tr.append('td').attr('class', 'num').text(function(d) { return pct(d.vote_share); });
  tr.append('td').attr('class', 'num').text(function(d) { return pct(d.seat_share); });
  tr.append('td').text(function(d) {
    return party_labels[d.vote_winner] + ((d.seat_winner != d.vote_winner) ? ' *' : '');
  });

  var mismatches = rows.filter(function(d) { return d.seat_winner != d.vote_winner; })
    .map(function(d) { return d.year; })
    .reverse();
  if (mismatches.length > 0) {
    d3.select('#summary-note').text(
      '* In ' + mismatches.join(' and ') + ', the party that won the most seats did not win the most votes.');
  }
}
