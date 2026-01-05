-- Eski Layer Manager - Macro Button Installer/Uninstaller
-- Run this script to install, upgrade, or uninstall the Layer Manager macro button

(
    -- Version of the installer
    local installerVersion = "0.21.0 (2026-01-05 14:01)"

    -- Function to check if macro files exist
    fn macrosExist = (
        local macroDir = getDir #userMacros
        local layerMacroFile = macroDir + "\\EskiLayerManager.mcr"
        local exporterMacroFile = macroDir + "\\EskiLayerExporter.mcr"
        return (doesFileExist layerMacroFile) or (doesFileExist exporterMacroFile)
    )

    -- Function to uninstall existing macros and Python files
    fn uninstallMacro = (
        local success = false
        try (
            -- Delete macro files
            local macroDir = getDir #userMacros
            local macroFiles = #(
                macroDir + "\\EskiLayerManager.mcr",
                macroDir + "\\EskiLayerExporter.mcr"
            )

            for macroFile in macroFiles do (
                if doesFileExist macroFile then (
                    deleteFile macroFile
                    format "Deleted macro file: %\n" macroFile
                    success = true
                )
            )

            -- Delete Python files
            local scriptsDir = getDir #userScripts
            local pythonFiles = #(
                scriptsDir + "\\eski_layer_manager.py",
                scriptsDir + "\\eski_layer_exporter.py"
            )

            for pythonFile in pythonFiles do (
                if doesFileExist pythonFile then (
                    deleteFile pythonFile
                    format "Deleted Python file: %\n" pythonFile
                    success = true
                )
            )

            -- Reload macros to update action manager
            macros.load()

            return success
        ) catch (
            format "Error during uninstall: %\n" (getCurrentException())
            return false
        )
    )

    -- Function to find and copy a single Python script
    -- Parameters: sourceFileName (with hyphens), targetFileName (with underscores)
    fn copySinglePythonScript sourceFileName targetFileName = (
        -- Use user scripts directory, not system scripts directory
        local scriptsDir = getDir #userScripts
        local targetFile = scriptsDir + "\\" + targetFileName

        -- Get user profile path using systemTools
        local userProfile = systemTools.getEnvVariable "USERPROFILE"

        -- List of possible source locations to check
        local possiblePaths = #(
            -- Same directory as this installer script
            (getFilenamePath (getThisScriptFilename()) + sourceFileName),
            -- Current max file directory
            (maxFilePath + sourceFileName),
            -- Desktop
            (userProfile + "\\Desktop\\" + sourceFileName),
            -- Downloads folder
            (userProfile + "\\Downloads\\" + sourceFileName),
            -- Documents folder
            (userProfile + "\\Documents\\" + sourceFileName)
        )

        -- Try to find the source file
        local sourceFile = undefined
        format "Searching for % in:\n" sourceFileName
        for path in possiblePaths do (
            format "  Checking: %\n" path
            if doesFileExist path then (
                sourceFile = path
                format "  FOUND at: %\n" path
                exit
            )
        )

        -- If found, copy it
        if sourceFile != undefined then (
            try (
                format "Copying to: %\n" targetFile

                -- Ensure target directory exists
                local targetDir = getFilenamePath targetFile
                if not (doesDirectoryExist targetDir) then (
                    makeDir targetDir all:true
                    format "Created directory: %\n" targetDir
                )

                -- Delete existing file if present to avoid issues
                if doesFileExist targetFile then (
                    deleteFile targetFile
                    format "Deleted existing file\n"
                )

                -- Copy the file
                local copyResult = copyFile sourceFile targetFile
                format "Copy result: %\n" copyResult

                -- Verify it worked
                if doesFileExist targetFile then (
                    format "Copy successful! File exists at destination.\n"
                    return #(true, sourceFile)
                ) else (
                    format "ERROR: Copy reported success but file not found at destination!\n"
                    return #(false, "Copy completed but file not found at destination")
                )
            ) catch (
                local errMsg = getCurrentException()
                format "ERROR during copy: %\n" errMsg
                return #(false, "Copy failed: " + errMsg)
            )
        ) else (
            format "Source file NOT FOUND in any location\n"
            return #(false, "Source file not found in any of the searched locations")
        )
    )

    -- Function to copy all Python scripts
    fn copyPythonScripts = (
        local results = #()
        local allSuccess = true
        local errorMessages = #()

        -- Define files to copy: #(source_name, target_name)
        local filesToCopy = #(
            #("eski-layer-manager.py", "eski_layer_manager.py"),
            #("eski-layer-exporter.py", "eski_layer_exporter.py")
        )

        format "\n=== Copying Python files ===\n"
        for filePair in filesToCopy do (
            local sourceFileName = filePair[1]
            local targetFileName = filePair[2]

            local result = copySinglePythonScript sourceFileName targetFileName
            append results result

            if not result[1] then (
                allSuccess = false
                append errorMessages (sourceFileName + ": " + result[2])
            )
        )

        -- Return overall result
        if allSuccess then (
            return #(true, "All files copied successfully")
        ) else (
            local errorMsg = "Some files could not be copied:\n"
            for msg in errorMessages do (
                errorMsg += "  - " + msg + "\n"
            )
            return #(false, errorMsg)
        )
    )

    -- Function to install/upgrade the Layer Manager macro
    fn installLayerManagerMacro = (
        -- Create the macro script code
        local macroCode = "macroScript EskiLayerManager\n"
        macroCode += "    category:\"Eski Tools\"\n"
        macroCode += "    buttonText:\"Eski\\nLayers\"\n"
        macroCode += "    toolTip:\"Eski Layer Manager by Claude v" + installerVersion + "\"\n"
        macroCode += "    icon:#(\"AnimLayerToolbar\",10)\n"
        macroCode += "(\n"
        macroCode += "    -- This macro button launches the Eski Layer Manager\n"
        macroCode += "    try (\n"
        macroCode += "        python.Execute \"import sys\"\n"
        macroCode += "        python.Execute \"import importlib\"\n"
        macroCode += "        python.Execute \"import os\"\n"
        macroCode += "        \n"
        macroCode += "        -- Add user scripts directory to Python path if not already there\n"
        macroCode += "        local scriptsDir = getDir #userScripts\n"
        macroCode += "        python.Execute (\"scripts_dir = r'\" + scriptsDir + \"'\")\n"
        macroCode += "        python.Execute \"if scripts_dir not in sys.path: sys.path.insert(0, scripts_dir)\"\n"
        macroCode += "        \n"
        macroCode += "        -- Import module ONCE (preserves singleton pattern)\n"
        macroCode += "        -- The module has guards to prevent re-initialization\n"
        macroCode += "        python.Execute \"import eski_layer_manager\"\n"
        macroCode += "        \n"
        macroCode += "        -- Show the layer manager (singleton pattern ensures only one instance)\n"
        macroCode += "        python.Execute \"eski_layer_manager.show_layer_manager()\"\n"
        macroCode += "    ) catch (\n"
        macroCode += "        messageBox \"ERROR: Cannot find eski-layer-manager.py\\n\\nPlease make sure eski-layer-manager.py is copied to:\\n\" + (getDir #userScripts) + \"\\n\\nSee README.md for installation instructions.\" title:\"Eski Layer Manager - File Not Found\"\n"
        macroCode += "    )\n"
        macroCode += ")\n"

        -- Get user macro directory
        local macroDir = getDir #userMacros
        local macroFile = macroDir + "\\EskiLayerManager.mcr"

        try (
            -- Write macro file
            local f = createFile macroFile
            format macroCode to:f
            close f

            return true
        ) catch (
            return false
        )
    )

    -- Function to install/upgrade the Exporter macro
    fn installExporterMacro = (
        -- Create the macro script code for exporter
        local macroCode = "macroScript EskiLayerExporter\n"
        macroCode += "    category:\"Eski Tools\"\n"
        macroCode += "    buttonText:\"Eski\\nExporter\"\n"
        macroCode += "    toolTip:\"Eski Real-Time Exporter by Claude v" + installerVersion + "\"\n"
        macroCode += "    icon:#(\"Containers\",6)\n"
        macroCode += "(\n"
        macroCode += "    -- This macro button toggles the Eski Exporter\n"
        macroCode += "    try (\n"
        macroCode += "        python.Execute \"import sys\"\n"
        macroCode += "        python.Execute \"import importlib\"\n"
        macroCode += "        python.Execute \"import os\"\n"
        macroCode += "        \n"
        macroCode += "        -- Add user scripts directory to Python path if not already there\n"
        macroCode += "        local scriptsDir = getDir #userScripts\n"
        macroCode += "        python.Execute (\"scripts_dir = r'\" + scriptsDir + \"'\")\n"
        macroCode += "        python.Execute \"if scripts_dir not in sys.path: sys.path.insert(0, scripts_dir)\"\n"
        macroCode += "        \n"
        macroCode += "        -- Import module ONCE (preserves singleton pattern)\n"
        macroCode += "        python.Execute \"import eski_layer_exporter\"\n"
        macroCode += "        \n"
        macroCode += "        -- Toggle the exporter (show if hidden, close if visible)\n"
        macroCode += "        python.Execute \"\n"
        macroCode += "if eski_layer_exporter._exporter_instance is not None:\n"
        macroCode += "    try:\n"
        macroCode += "        if eski_layer_exporter._exporter_instance.isVisible():\n"
        macroCode += "            eski_layer_exporter._exporter_instance.close()\n"
        macroCode += "        else:\n"
        macroCode += "            eski_layer_exporter._exporter_instance.show()\n"
        macroCode += "            eski_layer_exporter._exporter_instance.raise_()\n"
        macroCode += "            eski_layer_exporter._exporter_instance.activateWindow()\n"
        macroCode += "    except:\n"
        macroCode += "        eski_layer_exporter._exporter_instance = None\n"
        macroCode += "        eski_layer_exporter.show_exporter()\n"
        macroCode += "else:\n"
        macroCode += "    eski_layer_exporter.show_exporter()\n"
        macroCode += "\"\n"
        macroCode += "    ) catch (\n"
        macroCode += "        messageBox \"ERROR: Cannot find eski-layer-exporter.py\\n\\nPlease make sure eski-layer-exporter.py is copied to:\\n\" + (getDir #userScripts) + \"\\n\\nSee README.md for installation instructions.\" title:\"Eski Exporter - File Not Found\"\n"
        macroCode += "    )\n"
        macroCode += ")\n"

        -- Get user macro directory
        local macroDir = getDir #userMacros
        local macroFile = macroDir + "\\EskiLayerExporter.mcr"

        try (
            -- Write macro file
            local f = createFile macroFile
            format macroCode to:f
            close f

            return true
        ) catch (
            return false
        )
    )

    -- Function to install both macros
    fn installMacros = (
        local layerSuccess = installLayerManagerMacro()
        local exporterSuccess = installExporterMacro()

        -- Reload macros once after both are created
        if layerSuccess or exporterSuccess then (
            macros.load()
        )

        return #(layerSuccess, exporterSuccess)
    )

    -- Function to get installed Python script version
    fn getInstalledVersion = (
        local scriptsDir = getDir #userScripts
        local pythonFile = scriptsDir + "\\eski_layer_manager.py"

        if doesFileExist pythonFile then (
            try (
                local f = openFile pythonFile mode:"r"
                local versionLine = ""
                -- Read first 10 lines to find version
                for i = 1 to 10 do (
                    local line = readLine f
                    if line != undefined and (matchPattern line pattern:"*Version:*") then (
                        versionLine = line
                        exit
                    )
                )
                close f

                if versionLine != "" then (
                    -- Extract version number (format: "Version: 0.4.7")
                    local parts = filterString versionLine ":"
                    if parts.count >= 2 then (
                        return (trimLeft (trimRight parts[2]))
                    )
                )
            ) catch ()
        )
        return "Unknown"
    )

    -- Create the installer dialog
    rollout eskiInstallerDialog ("Eski Layer Manager Installer v" + installerVersion) width:400 height:600 (

        label lblTitle "Eski Layer Manager - Macro Button Setup" align:#center style_sunkenedge:true offset:[0,10]
        label lblVersion "" align:#center offset:[0,5]

        groupBox grpStatus "Current Status" pos:[10,60] width:380 height:420
        editText lblStatus "" pos:[20,80] width:360 height:390 align:#left readOnly:true

        button btnInstall "Install / Upgrade to Latest Version" pos:[10,490] width:380 height:45
        button btnUninstall "Uninstall Current and Older Versions" pos:[10,545] width:380 height:45

        -- Function to compare version strings (returns true if v1 < v2)
        fn isNewerVersion v1 v2 = (
            if v1 == "Unknown" then return true
            if v2 == "Unknown" then return false

            -- Split version strings by dots
            local v1Parts = filterString v1 "."
            local v2Parts = filterString v2 "."

            -- Compare each part
            for i = 1 to (amax v1Parts.count v2Parts.count) do (
                local part1 = if i <= v1Parts.count then (v1Parts[i] as integer) else 0
                local part2 = if i <= v2Parts.count then (v2Parts[i] as integer) else 0

                if part1 < part2 then return true
                if part1 > part2 then return false
            )

            return false  -- versions are equal
        )

        -- Check status on open
        on eskiInstallerDialog open do (
            -- Set version label dynamically
            lblVersion.text = "Installer Version: " + installerVersion

            local statusText = ""
            local installedVersion = getInstalledVersion()

            if macrosExist() then (
                statusText = "STATUS: Macro buttons are currently INSTALLED\n\n"
                statusText += "Category: Eski Tools\n"
                statusText += "Buttons: EskiLayerManager, EskiLayerExporter\n"
                statusText += "Installed Version: " + installedVersion + "\n"
                statusText += "Installer Version: " + installerVersion + "\n\n"

                -- Check if update is available
                if isNewerVersion installedVersion installerVersion then (
                    statusText += "⚠ UPDATE AVAILABLE!\n"
                    statusText += "Click 'Install / Upgrade' to update to v" + installerVersion
                ) else if installedVersion == installerVersion then (
                    statusText += "✓ You have the latest version"
                ) else (
                    statusText += "ℹ Installed version is newer than installer"
                )
            ) else (
                statusText = "STATUS: Macro button is NOT installed\n\n"
                statusText += "No macro found in 'Eski Tools' category\n"
                if installedVersion != "Unknown" then (
                    statusText += "\nPython script found (version " + installedVersion + ") but macro not installed"
                )
            )

            lblStatus.text = statusText
        )

        -- Install/Upgrade button
        on btnInstall pressed do (
            local wasInstalled = macrosExist()
            local statusText = ""

            -- Close any existing Layer Manager window before upgrade
            try (
                local closeScript = "
import sys
if 'eski_layer_manager' in sys.modules:
    import eski_layer_manager
    if hasattr(eski_layer_manager, '_layer_manager_instance') and eski_layer_manager._layer_manager_instance[0] is not None:
        try:
            if eski_layer_manager._layer_manager_instance[0].isVisible():
                eski_layer_manager._layer_manager_instance[0].close()
                print('[INSTALLER] Closed existing Layer Manager window')
        except Exception as e:
            print('[INSTALLER] Could not close window: ' + str(e))
"
                python.Execute closeScript
                statusText += "✓ Closed existing Layer Manager window\n"
            ) catch (
                format "[INSTALLER] Error closing window: %\n" (getCurrentException())
            )

            -- First, try to copy the Python scripts
            local copyResult = copyPythonScripts()
            local pythonCopied = copyResult[1]

            if pythonCopied then (
                statusText += "✓ Python scripts copied successfully\n"
                statusText += "  " + copyResult[2] + "\n"
            ) else (
                statusText += "⚠ WARNING: Could not copy all Python files\n"
                statusText += copyResult[2]
                statusText += "  You may need to manually copy missing files to:\n"
                statusText += "  " + (getDir #userScripts) + "\n"
            )

            -- Reload the Python module to pick up changes
            local reloadSuccess = false
            if pythonCopied then (
                try (
                    python.Execute "import importlib"
                    python.Execute "if 'eski_layer_manager' in sys.modules: importlib.reload(sys.modules['eski_layer_manager'])"
                    statusText += "✓ Python module reloaded\n\n"
                    reloadSuccess = true
                ) catch (
                    statusText += "⚠ Could not reload Python module\n\n"
                )
            ) else (
                statusText += "\n"
            )

            local macroResults = installMacros()
            local layerSuccess = macroResults[1]
            local exporterSuccess = macroResults[2]

            if layerSuccess or exporterSuccess then (
                -- Delay to allow macros to fully reload
                windows.processPostedMessages()

                local installedVersion = getInstalledVersion()

                if wasInstalled then (
                    statusText += "✓ Macro buttons UPGRADED successfully!\n\n"
                    statusText += "Installed Version: " + installedVersion + "\n"
                    statusText += "Category: Eski Tools\n"
                    if layerSuccess then (
                        statusText += "  • EskiLayerManager (Layer Manager)\n"
                    )
                    if exporterSuccess then (
                        statusText += "  • EskiLayerExporter (Real-Time Exporter)\n"
                    )
                    statusText += "\n"

                    -- Launch the new version if reload was successful
                    if reloadSuccess then (
                        try (
                            python.Execute "import eski_layer_manager; eski_layer_manager.show_layer_manager()"
                            statusText += "✓ Layer Manager launched with new version!\n"
                        ) catch (
                            statusText += "Changes are live! Click your toolbar buttons\n"
                            statusText += "to launch the updated tools.\n"
                        )
                    ) else (
                        statusText += "Changes are live! Click your toolbar buttons\n"
                        statusText += "to launch the updated tools.\n"
                    )
                ) else (
                    statusText += "✓ Macro buttons INSTALLED successfully!\n\n"
                    statusText += "Installed Version: " + installedVersion + "\n"
                    statusText += "Category: Eski Tools\n"
                    if layerSuccess then (
                        statusText += "  • EskiLayerManager (Layer Manager)\n"
                    )
                    if exporterSuccess then (
                        statusText += "  • EskiLayerExporter (Real-Time Exporter)\n"
                    )
                    statusText += "\nNEXT STEPS:\n"
                    statusText += "1. Press Y or go to:\n"
                    statusText += "   Customize > Customize User Interface\n"
                    statusText += "2. Select category: 'Eski Tools'\n"
                    statusText += "3. Drag 'EskiLayerManager' and/or 'EskiLayerExporter'\n"
                    statusText += "   to any toolbar\n"
                    statusText += "4. Click Save and Close\n\n"
                    statusText += "Then click the button to launch the Layer Manager!\n\n"
                    statusText += "Tip: You can assign a keyboard shortcut in:\n"
                    statusText += "Customize > Customize User Interface > Keyboard tab"
                )

                -- Update status window
                lblStatus.text = statusText
            ) else (
                statusText += "✗ Installation FAILED!\n\n"
                statusText += "Could not create macro file.\n"
                statusText += "Check permissions and try again."
                lblStatus.text = statusText
            )
        )

        -- Uninstall button
        on btnUninstall pressed do (
            if macrosExist() then (
                if queryBox "Are you sure you want to UNINSTALL Eski Tools?\n\nThis will remove:\n- Macro button files (.mcr)\n- Python script files (.py)\n- Requires 3ds Max restart to fully clear actions\n\n(You can reinstall anytime by running this script again)" title:"Confirm Uninstall" then (
                    if uninstallMacro() then (
                        local statusText = "✓ Files REMOVED successfully!\n\n"
                        statusText += "✓ Macro button file deleted\n"
                        statusText += "✓ Python script deleted\n\n"
                        statusText += "NEXT STEPS - Complete Removal:\n\n"
                        statusText += "1. Close this dialog\n"
                        statusText += "2. Remove button from toolbars (if present)\n"
                        statusText += "3. Remove keyboard shortcuts\n"
                        statusText += "   (Customize > Keyboard tab)\n"
                        statusText += "4. RESTART 3ds Max\n\n"
                        statusText += "After restart, the action will be completely\n"
                        statusText += "removed from the Customize User Interface lists."

                        -- Update status window
                        lblStatus.text = statusText
                    ) else (
                        local statusText = "✗ Uninstallation FAILED!\n\n"
                        statusText += "Could not remove files.\n"
                        statusText += "Check listener for details."
                        lblStatus.text = statusText
                    )
                )
            ) else (
                local statusText = "⚠ Nothing to uninstall\n\n"
                statusText += "The Eski Layer Manager macro is not currently installed."
                lblStatus.text = statusText
            )
        )
    )

    -- Show the dialog (non-modal so it doesn't block the UI)
    createDialog eskiInstallerDialog modal:false
)
