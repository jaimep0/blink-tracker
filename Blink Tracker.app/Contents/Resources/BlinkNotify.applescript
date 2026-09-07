-- BlinkNotify: posts a default macOS notification banner attributed to this applet.
-- Icon comes from Contents/Resources/applet.icns (copied from AppIcon.icns at build time).
on run argv
	if (count of argv) < 2 then
		return
	end if
	set theTitle to item 1 of argv as text
	set theBody to item 2 of argv as text
	display notification theBody with title theTitle
end run
