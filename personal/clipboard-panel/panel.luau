--!nonstrict
-- Noctalia draws the panel and controls with the current shell palette.
local opened = false
local generation = 0
local entries = {}
local matches = {}
local query = ""
local selected = 1
local preview = {}
local previewId = nil
local previewSession = ""
local busy = false
local errorText = ""
local render
local refreshPreview
local backend = noctalia.pluginDir() .. "/backend.py"

local function call(args, callback)
  local command = { "python3", backend }
  for _, value in ipairs(args) do table.insert(command, value) end
  noctalia.runAsync(command, callback)
end

local function chosen()
  return matches[selected]
end

local function copySelected()
  local entry = chosen()
  if not entry or busy then return end
  busy = true
  local current = generation
  call({ "copy", entry.id }, function(result)
    if not opened or current ~= generation then return end
    busy = false
    if result.exitCode == 0 then
      panel.close()
    else
      errorText = "这条记录已失效，请重新打开历史。"
      render()
    end
  end)
end

refreshPreview = function()
  local entry = chosen()
  if not entry then
    preview = {}
    previewId = nil
    return
  end
  if previewId == entry.id then return end
  previewId = entry.id
  preview = {}
  local current = generation
  local requested = entry.id
  local session = previewSession
  call({ "preview", requested, session }, function(result)
    if not opened or current ~= generation then
      call({ "clear-preview", session })
      return
    end
    if previewId ~= requested then return end
    if result.exitCode == 0 then
      preview = noctalia.json.decode(result.stdout) or {}
    else
      preview = { text = "预览不可用" }
    end
    render()
  end)
end

local function filter()
  matches = {}
  for _, entry in ipairs(entries) do
    if query == "" or noctalia.fuzzyScore(query, entry.text) ~= nil then
      table.insert(matches, entry)
    end
  end
  selected = 1
  refreshPreview()
  render()
end

render = function()
  if not opened then return end
  local rows = {}
  local pageSize = 5
  local first = math.floor((selected - 1) / pageSize) * pageSize + 1
  for index = first, math.min(first + pageSize - 1, #matches) do
    local entry = matches[index]
    local active = index == selected
    table.insert(rows, ui.row({
      key = entry.id, gap = 10, align = "center", paddingH = 12, paddingV = 10,
      radius = 12, fill = active and "primary/0.18" or "surface_container/0.12",
      minHeight = 54,
      onClick = function()
        selected = index
        refreshPreview()
        copySelected()
      end,
      onHover = function(state)
        if state == "true" and selected ~= index then
          selected = index
          refreshPreview()
          render()
        end
      end,
    }, {
      ui.glyph({ name = entry.image and "photo" or "align-left", size = 20,
                 color = active and "primary" or "on_surface_variant" }),
      ui.label({ text = entry.text, fontSize = 13, color = "on_surface",
                 maxLines = 2, maxWidth = 320, flexGrow = 1 }),
    }))
  end
  if #rows == 0 then
    table.insert(rows, ui.label({ text = #entries == 0 and "暂无共享历史" or "没有匹配的记录",
                                 color = "on_surface_variant", textAlign = "center" }))
  end
  local details = {
    ui.label({ text = chosen() and (chosen().image and "图片预览" or "文字预览") or "预览",
               fontSize = 13, fontWeight = "semibold", color = "on_surface_variant" }),
  }
  if preview.path then
    table.insert(details, ui.image({ path = preview.path, width = 280, height = 300,
                                    fit = "contain", radius = 12 }))
  else
    table.insert(details, ui.scroll({ flexGrow = 1 }, {
      ui.label({ text = preview.text or (chosen() and "正在读取…" or ""),
                 maxWidth = 272, fontSize = 13, color = "on_surface", maxLines = 80 }),
    }))
  end
  table.insert(details, ui.spacer({ flexGrow = 1 }))
  table.insert(details, ui.button({ text = busy and "正在复制…" or "复制", glyph = "copy",
                                   variant = "primary", enabled = chosen() ~= nil and not busy,
                                   onClick = copySelected }))
  panel.render(ui.column({ gap = 14, flexGrow = 1 }, {
    ui.row({ gap = 10, align = "center" }, {
      ui.glyph({ name = "clipboard", size = 24, color = "primary" }),
      ui.label({ text = "剪贴板", fontSize = 20, fontWeight = "semibold", flexGrow = 1 }),
      ui.label({ text = tostring(#matches) .. " 条", fontSize = 12, color = "on_surface_variant" }),
      ui.button({ glyph = "x", variant = "ghost", onClick = panel.close }),
    }),
    ui.input({ key = "search-" .. tostring(generation), placeholder = "搜索文字或图片…",
               focus = true, value = query,
               onChange = function(value) query = value; filter() end,
               onSubmit = copySelected }),
    ui.row({ gap = 16, flexGrow = 1, align = "stretch" }, {
      ui.column({ width = 384, gap = 8, flexGrow = 1 }, {
        ui.scroll({ gap = 6, flexGrow = 1 }, rows),
        ui.row({ align = "center", gap = 8 }, {
          ui.button({ glyph = "chevron-left", variant = "ghost", enabled = first > 1,
                      onClick = function() selected = math.max(1, first - pageSize); refreshPreview(); render() end }),
          ui.label({ text = #matches == 0 and "0 / 0" or tostring(selected) .. " / " .. tostring(#matches),
                     fontSize = 11, color = "on_surface_variant", flexGrow = 1, textAlign = "center" }),
          ui.button({ glyph = "chevron-right", variant = "ghost", enabled = first + pageSize <= #matches,
                      onClick = function() selected = math.min(#matches, first + pageSize); refreshPreview(); render() end }),
        }),
      }),
      ui.separator({ orientation = "vertical", color = "outline_variant/0.3" }),
      ui.column({ width = 280, gap = 12 }, details),
    }),
    ui.label({ text = errorText ~= "" and errorText or "↑ ↓ 选择  ·  Enter 复制  ·  Ctrl+V 粘贴  ·  Super+V / Esc 关闭",
               fontSize = 11, color = errorText ~= "" and "error" or "on_surface_variant" }),
  }))
end

function onOpen(_context)
  generation += 1
  previewSession = tostring(noctalia.nowMs()) .. "-" .. tostring(generation)
  opened = true
  entries = {}
  matches = {}
  query = ""
  selected = 1
  preview = {}
  previewId = nil
  busy = false
  errorText = ""
  local current = generation
  render()
  call({ "list" }, function(result)
    if not opened or current ~= generation then return end
    if result.exitCode == 0 then
      entries = noctalia.json.decode(result.stdout) or {}
    else
      errorText = "无法读取共享历史。"
    end
    filter()
  end)
end

function onClose()
  opened = false
  generation += 1
  entries = {}
  matches = {}
  preview = {}
  previewId = nil
  call({ "clear-preview", previewSession })
end

function onKey(chord, pressed)
  if not pressed or #matches == 0 then return end
  local delta = (chord == "Down" or chord == "ctrl+j") and 1 or -1
  selected = math.clamp(selected + delta, 1, #matches)
  refreshPreview()
  render()
end
