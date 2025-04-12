require "custom.autocmd"

-- GotoTab
-- This utilizes the vim.t.bufs tab table variable where we store buffer numbers of current tab.
-- Then it loops from 1-9 to create mappings of switching tab by number i.e Alt+1 will switch first tab.
-- https://nvchad.com/docs/api
for i = 1, 9, 1 do
  vim.keymap.set("n", string.format("<A-%s>", i), function()
    vim.api.nvim_set_current_buf(vim.t.bufs[i])
  end)
end
