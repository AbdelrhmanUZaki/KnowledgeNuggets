require "nvchad.mappings"

local opts = { noremap = true, silent = true }
-- add yours here

local map = vim.keymap.set

-- Zaki custom mappings

-- Basic Tab Mappings
map("n", "<leader>tn", ":tabnew<CR>", opts)
map("n", "<leader>tc", ":tabclose<CR>", opts)
map("n", "<leader>tl", ":tabnext<CR>", opts)
map("n", "<leader>th", ":tabprevious<CR>", opts)

-- Close file

map("n", "<leader>q", "<cmd>q<CR>", opts, { desc = "Close buffer" })
map("n", "<leader>qq", "<cmd>qa<CR>", opts, { desc = "Close all buffers" })

-- Navigate in file
map("n", "<C-d>", "<C-d>zz", opts, { desc = "Move down and center" })
map("n", "<C-u>", "<C-u>zz", opts, { desc = "Move up and center" })
map("n", "n", "nzzzv", opts, { desc = "Find next and center" })
map("n", "N", "Nzzzv", opts, { desc = "Find previous and center" })

-- Resizing
map("n", "<C-Up>", ":resize +2<CR>", opts)
map("n", "<C-Down>", ":resize -2<CR>", opts)
map("n", "<C-Right>", ":vertical resize +2<CR>", opts)
map("n", "<C-Left>", ": vertical resize -2<CR>", opts)

-- split
-- map("n",'<leader>/', "<C-w>v", opts) -- This mapping is used for gcc

-- Save file
map({ "n", "i", "v", "x" }, "<C-s>", "<cmd>w<CR>", opts)

-- Select all
map("n", "<C-a>", "gg<S-v>G", opts)

-- split
map("n", "sv", "<C-w>v", opts)
map("n", "ss", "<C-w>s", opts)

-- Move focus
map("n", "sh", "<C-w>h", opts)
map("n", "sj", "<C-w>j", opts)
map("n", "sk", "<C-w>k", opts)
map("n", "sl", "<C-w>l", opts)

-- Navigate buffers
map("n", "<S-l>", ":bnext<CR>", opts)
map("n", "<S-h>", ":bprevious<CR>", opts)

-- Move text up and down in visual mode
map("n", "<A-j>", "<cmd>m .+1<cr>==", opts, { desc = "Move Down in NORMAL mode" })
map("n", "<A-k>", "<cmd>m .-2<cr>==", opts, { desc = "Move Up in NORMAL mode" })

map("v", "<A-j>", ":m '>+1<CR>gv=gv", opts, { desc = "Move Down in VISUAL mode " })
map("v", "<A-k>", ":m '<-2<CR>gv=gv", opts, { desc = "Move Up in VISUAL mode " })

map("i", "<A-j>", "<Esc>:m .+1<CR>==gi", opts, { desc = "Move Down in INSERT mode" })
map("i", "<A-k>", "<Esc>:m .-2<CR>==gi", opts, { desc = "Move Up INSERT mode" })

-- Indentation
map("v", "<", "<gv", opts)
map("v", ">", ">gv", opts)

map("x", "<leader>p", '"_dp', opts, { desc = "Paste without yanking in visual mode" })

-- map("n", "<leader>ui", vim.show_pos, { desc = "Inspect Pos" })

map("n", "gx", [[:lua OpenUrl()<CR>]], opts)

function OpenUrl()
  local url = vim.fn.expand "<cWORD>"
  if string.match(url, "^https?://") or string.match(url, "^www%.") then
    vim.fn.jobstart({ "xdg-open", url }, { detach = true })
  else
    print "No URL found under cursor"
  end
end
