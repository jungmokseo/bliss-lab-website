// Execute this function inside functions.exec with the connected Notion tools.
// Output only counts and a private snapshot path, never page content.
async (tools, sources, outputDir) => {
  const fields = {
    publications: ['Name', 'Number', 'Year', 'Authors', 'Journal', 'Image Path',
      'DOI Link', 'Impact Factor', 'Status', 'Type', 'Awards', 'Press', 'Press EN', 'Press Link'],
    patents: ['Name', 'Title (EN)', 'Inventors', 'Inventors EN', 'Patent Number', 'Year', 'Status', 'Status EN', 'Country'],
    team: ['Name', 'Name EN', 'Role', 'Active', 'Email', 'Order', 'Year Joined', 'Research Topic', 'Photo'],
    news: ['Name', 'Name EN', 'date:Date:start', 'Category', 'Image', 'Public Summary KR', 'Summary EN'],
    highlights: ['Name', 'Title KR', 'Title EN', 'Description', 'Description EN', 'Visible',
      'Publication Number', 'Order', 'Tag', 'Journal Citation'],
  };
  const skill = 'notion-website-sync';
  function unpack(result, context) {
    if (result.isError) throw Error(context + ' failed; check Notion access or schema.');
    const raw = result.content?.find(x => x.type === 'text')?.text;
    const data = result.structuredContent || (raw ? JSON.parse(raw) : null);
    if (!data || typeof data !== 'object') throw Error(context + ' returned no structured data.');
    return data;
  }
  const access = unpack(await tools.mcp__codex_apps__notion_notion_get_tool_access({
    tool_names: ['query_data_sources'], skill,
  }), 'Notion access');
  const available = access.current_tool_access?.query_data_sources?.status;
  if (available !== 'available' && available !== 'available_with_limit') {
    throw Error('Notion data source queries are unavailable for this connection.');
  }

  const all = {};
  for (const [key, cols] of Object.entries(fields)) {
    const id = sources[key];
    if (!/^[0-9a-f-]{36}$/.test(id || '')) throw Error('Missing configured source ' + key);
    const url = 'collection://' + id;
    const schema = unpack(await tools.mcp__codex_apps__notion_fetch({id:url, skill}), key + ' schema');
    const sqlSchema = schema.text?.match(/<sqlite-table>([\s\S]*?)<\/sqlite-table>/)?.[1];
    if (!sqlSchema || cols.some(c => !sqlSchema.includes('"' + c + '"'))) {
      throw Error(key + ' schema changed; no snapshot was written.');
    }

    const run = async query => unpack(await tools.mcp__codex_apps__notion_query_data_sources({
      data: {data_source_urls: [url], mode: 'sql', query}, skill,
    }), key + ' query');
    const table = '"' + url + '"';
    const getCount = async () => Number((await run('SELECT COUNT(*) AS n FROM ' + table)).results?.[0]?.n);
    const total = await getCount();
    if (!Number.isSafeInteger(total) || total < 1 || total > 5000) {
      throw Error(key + ' returned an invalid row count.');
    }
    const rows = [];
    const seen = new Set();
    const limit = 50;
    const columnList = cols.map(c => '"' + c + '"').join(', ');
    for (let offset = 0; offset < total; offset += limit) {
      const d = await run('SELECT url, ' + columnList + ' FROM ' + table +
        ' ORDER BY url LIMIT ' + limit + ' OFFSET ' + offset);
      if (d.has_more || !Array.isArray(d.results) || d.results.length !== Math.min(limit, total - offset)) {
        throw Error(key + ' returned a truncated or changing page.');
      }
      for (const {url: pageUrl, ...row} of d.results) {
        const pageId = pageUrl?.match(/\/([0-9a-f]{32})(?:\?|$)/i)?.[1]?.toLowerCase();
        if (!pageId || seen.has(pageId)) throw Error(key + ' returned a missing or duplicate page ID.');
        seen.add(pageId);
        rows.push(Object.fromEntries([['_id', pageId], ...cols.map(c => {
          const value = row[c];
          return [c, value === '__YES__' ? true : value === '__NO__' ? false : value ?? null];
        })]));
      }
    }
    if (await getCount() !== total) throw Error(key + ' changed while being read; retry next run.');
    all[key] = rows;
  }
  if (!outputDir.startsWith('/') || outputDir.includes('\n')) throw Error('Use an absolute private output directory.');
  const now = new Date();
  const path = outputDir + '/snapshot-' + now.getTime() + '.json';
  const snapshot = JSON.stringify({version: 1, captured_at: now.toISOString(), sources: all}, null, 2);
  const patch = '*** Begin Patch\n*** Add File: ' + path + '\n+' + snapshot.replace(/\n/g, '\n+') + '\n*** End Patch';
  const written = await tools.apply_patch(patch);
  if (written?.isError) throw Error('Could not save private snapshot.');
  const mode = await tools.exec_command({
    cmd: "chmod 600 '" + path.replace(/'/g, "'\\''") + "'",
    max_output_tokens: 100,
  });
  if (mode.exit_code !== 0) throw Error('Private snapshot file is unavailable.');
  return {path, counts:Object.fromEntries(Object.entries(all).map(([k,v])=>[k,v.length]))};
}
