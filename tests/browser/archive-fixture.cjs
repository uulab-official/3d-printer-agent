// Synthetic Studio export structures, never manufacturer printing profiles.
// Stored ZIP members keep the exact text available for byte-hash assertions.
function crc32(bytes) {
  let crc = 0xffffffff;
  for (const value of bytes) {
    crc ^= value;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function zipMembers(members) {
  const files = [], directory = [];
  let offset = 0;
  for (const { path, text } of members) {
    const name = Buffer.from(path, 'utf8'), body = Buffer.from(text, 'utf8');
    const crc = crc32(body);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0x800, 6);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(body.length, 18);
    local.writeUInt32LE(body.length, 22);
    local.writeUInt16LE(name.length, 26);
    files.push(local, name, body);
    const entry = Buffer.alloc(46);
    entry.writeUInt32LE(0x02014b50, 0);
    entry.writeUInt16LE(20, 4);
    entry.writeUInt16LE(20, 6);
    entry.writeUInt16LE(0x800, 8);
    entry.writeUInt32LE(crc, 16);
    entry.writeUInt32LE(body.length, 20);
    entry.writeUInt32LE(body.length, 24);
    entry.writeUInt16LE(name.length, 28);
    entry.writeUInt32LE(offset, 42);
    directory.push(entry, name);
    offset += local.length + name.length + body.length;
  }
  const central = Buffer.concat(directory), end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(members.length, 8);
  end.writeUInt16LE(members.length, 10);
  end.writeUInt32LE(central.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...files, central, end]);
}

function filamentArchive(name, members) {
  const manifest = {
    version: '', bundle_id: 'offline_synthetic', bundle_type: 'filament config bundle',
    filament_name: 'Synthetic filament',
    filament_vendor: [{ vendor: 'Example', filament_path: members.map(member => member.path) }],
  };
  return { name, mimeType: 'application/zip', buffer: zipMembers([{ path: 'bundle_structure.json', text: JSON.stringify(manifest) }, ...members]) };
}

function printerArchive(name, filamentMember) {
  const manifest = {
    version: '', bundle_id: 'offline_synthetic', bundle_type: 'printer config bundle', printer_preset_name: 'Synthetic Printer',
    printer_config: ['printer/Printer.json'], filament_config: [filamentMember.path], process_config: ['process/Process.json'],
  };
  return { name, mimeType: 'application/zip', buffer: zipMembers([
    { path: 'bundle_structure.json', text: JSON.stringify(manifest) }, filamentMember,
    { path: 'printer/Printer.json', text: JSON.stringify({ name: 'Synthetic Printer', printer_settings_id: 'Synthetic Printer' }) },
    { path: 'process/Process.json', text: JSON.stringify({ name: 'Synthetic Process', print_settings_id: 'Synthetic Process' }) },
  ]) };
}

module.exports = { filamentArchive, printerArchive };
