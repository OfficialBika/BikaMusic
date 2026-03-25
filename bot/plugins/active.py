import os

from pyrogram import filters, types

from bot import app, db, lang, queue


@app.on_message(filters.command(["ac", "activevc"]) & app.sudoers)
@lang.language()
async def _activevc(_, m: types.Message):
    if not db.call_cache:
        return await m.reply_text(m.lang["vc_empty"])

    if m.command[0] == "ac":
        return await m.reply_text(m.lang["vc_count"].format(len(db.call_cache)))

    sent = await m.reply_text(m.lang["vc_fetching"])
    text = ""

    for index, chat_id in enumerate(db.call_cache):
        playing = queue.get_current(chat_id)
        if not playing:
            continue
        text += f"\n{index + 1}. <code>{chat_id}</code>\n    ➜ {playing.title[:25]}"

    if len(text) < 4000:
        return await sent.edit_text(m.lang["vc_list"] + text)

    with open("activevc.txt", "w", encoding="utf-8") as file:
        file.write(text)

    await sent.edit_media(
        media=types.InputMediaDocument(
            media="activevc.txt",
            caption=m.lang["vc_list"],
        )
    )
    os.remove("activevc.txt")
