return {
  {
    "akinsho/toggleterm.nvim",
    version = "*",
    cmd = { "ToggleTerm" },
    config = function()
      local toggleterm = require("toggleterm")
      toggleterm.setup({
        close_on_exit = true,
        shell = vim.o.shell,
      })

      local Terminal  = require("toggleterm.terminal").Terminal

      -- خليهم global
      _G.horiz_term = Terminal:new({
        direction = "horizontal",
        hidden = true,
      })

      _G.vert_term = Terminal:new({
        direction = "vertical",
        hidden = true,
      })

      _G.float_term = Terminal:new({
        direction = "float",
        hidden = true,
      })

      -- Map shortcuts Alt + key
      vim.api.nvim_set_keymap("n", "<A-h>", "<cmd>lua _G.horiz_term:toggle()<CR>", { noremap = true, silent = true })
      vim.api.nvim_set_keymap("n", "<A-v>", "<cmd>lua _G.vert_term:toggle()<CR>", { noremap = true, silent = true })
      vim.api.nvim_set_keymap("n", "<A-i>", "<cmd>lua _G.float_term:toggle()<CR>", { noremap = true, silent = true })
    end,
  },
}
