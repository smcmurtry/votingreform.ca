create_dropdown('#election-dropdown', elections);
create_dropdown('#voting-system-dropdown', voting_systems);
create_dropdown('#region-dropdown', regions);

// Seven files per election: seat totals, vote/seat shares, and one seat list
// per voting system. The 2015 files sit in data/, later elections in data/<year>/.
var years = elections.map(function(d) { return d.abbr; });
var seat_files = ['fptp', 'dmp', 'mmp', 'irv', 'stv'];
var files_per_year = 2 + seat_files.length;

var q = d3.queue().defer(d3.json, './data/elections_summary.json');

years.forEach(function(year) {
  var dir = (year == contributed_year) ? './data/' : './data/' + year + '/';
  q.defer(d3.json, dir + 'tot_summary.json')
    .defer(d3.csv, dir + 'pct_summary.csv', bars.type);
  seat_files.forEach(function(name) {
    q.defer(d3.csv, dir + name + '_clean.csv', blocks.type);
  });
});

q.awaitAll(function(error, files) {
  if (error) { throw error; }

  var summary = files[0];

  // store[year] = {tot: seats by region/system, pct: share rows, dataz: seat rows}
  var store = {};
  years.forEach(function(year, i) {
    var offset = 1 + files_per_year*i;
    store[year] = {
      tot: files[offset],
      pct: files[offset+1],
      dataz: blocks.prep({
        FPTP: files[offset+2], DMP: files[offset+3], MMP: files[offset+4],
        IRV: files[offset+5], STV: files[offset+6]
      })
    };
  });

  page_w = +d3.select('#main').style('width').slice(0,-2);
  table.init();
  bars.init();
  blocks.init();
  draw_summary(summary);

  d3.selectAll('#controls select').on('change', update_all);

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
    // Text that only applies to the contributed 2015 results, or only to our own simulations.
    d3.selectAll('.only-contributed').style('display', (sel_year == contributed_year) ? 'inline' : 'none');
    d3.selectAll('.only-simulated').style('display', (sel_year == contributed_year) ? 'none' : 'inline');
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
