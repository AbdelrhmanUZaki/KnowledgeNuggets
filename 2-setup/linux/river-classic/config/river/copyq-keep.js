// CopyQ automatic command: re-own each new clipboard selection so it survives
// the source client exiting (Wayland drops a selection when its owner dies).
//
// copy(item) adds CopyQ's mimeOwner marker, so CopyQ ignores its own re-copy and
// the automatic command cannot loop. Keep the offer small: all non-image
// formats plus exactly one image format (PNG when available) — copying Qt's
// synthetic image conversions (image/bmp, image/jpeg, ...) bloats the offer and
// can take the server down. Also skip anything already marked as CopyQ-owned:
// re-copying an owned image from CopyQ's own history crashed CopyQ 13 under
// Qt 6.10/river (CopyQ 17 is stable, but the guard is still correct).
var keepName = 'Keep clipboard after source exits';
var cmds = commands().filter(function(c) { return c.name !== keepName; });
cmds.unshift({
    name: keepName,
    automatic: true,
    input: '',
    cmd: [
        'copyq:',
        'if (!isClipboard()) { abort(); }',
        'var src = dataFormats();',
        'if (src.indexOf("application/x-copyq-owner") !== -1) { abort(); }',
        'var item = {};',
        'var hasPng = src.indexOf("image/png") !== -1;',
        'var imageDone = false;',
        'for (var i = 0; i < src.length; ++i) {',
        '    var m = src[i];',
        '    if (m.indexOf("application/x-copyq-") === 0) continue;',
        '    if (m === "application/x-qt-image") continue;',
        '    if (m.indexOf("image/") === 0) {',
        '        if (imageDone) continue;',
        '        if (hasPng && m !== "image/png") continue;',
        '        item[m] = data(m);',
        '        imageDone = true;',
        '        continue;',
        '    }',
        '    item[m] = data(m);',
        '}',
        'if (Object.keys(item).length > 0) copy(item);'
    ].join('\n')
});
setCommands(cmds);
