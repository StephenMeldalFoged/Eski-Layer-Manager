-- Eski Layer Manager - Macro Button Installer/Uninstaller
-- Run this script to install, upgrade, or uninstall the Layer Manager macro button

(
    -- Version of the installer
    local installerVersion = "0.3.5"

    -- Function to check if macro file exists
    fn macroExists = (
        local macroDir = getDir #userMacros
        local macroFile = macroDir + "\\EskiLayerManager.mcr"
        return doesFileExist macroFile
    )

    -- Function to uninstall existing macros and Python files
    fn uninstallMacro = (
        local success = false
        try (
            -- Delete macro file
            local macroDir = getDir #userMacros
            local macroFile = macroDir + "\\EskiLayerManager.mcr"

            if doesFileExist macroFile then (
                deleteFile macroFile
                format "Deleted macro file: %\n" macroFile
                success = true
            )

            -- Delete Python file
            local scriptsDir = getDir #userScripts
            local pythonFile = scriptsDir + "\\eski_layer_manager.py"

            if doesFileExist pythonFile then (
                deleteFile pythonFile
                format "Deleted Python file: %\n" pythonFile
                success = true
            )

            -- Reload macros to update action manager
            macros.load()

            return success
        ) catch (
            format "Error during uninstall: %\n" (getCurrentException())
            return false
        )
    )

    -- Function to find and copy the Python script
    fn copyPythonScript = (
        -- Use user scripts directory, not system scripts directory
        local scriptsDir = getDir #userScripts
        local targetFile = scriptsDir + "\\eski_layer_manager.py"

        -- Get user profile path using systemTools
        local userProfile = systemTools.getEnvVariable "USERPROFILE"

        -- List of possible source locations to check
        local possiblePaths = #(
            -- Same directory as this installer script
            (getFilenamePath (getThisScriptFilename()) + "eski-layer-manager.py"),
            -- Current max file directory
            (maxFilePath + "eski-layer-manager.py"),
            -- Desktop
            (userProfile + "\\Desktop\\eski-layer-manager.py"),
            -- Downloads folder
            (userProfile + "\\Downloads\\eski-layer-manager.py"),
            -- Documents folder
            (userProfile + "\\Documents\\eski-layer-manager.py")
        )

        -- Try to find the source file
        local sourceFile = undefined
        format "Searching for eski-layer-manager.py in:\n"
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

    -- Function to install/upgrade the macro
    fn installMacro = (
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

            -- Reload macros
            macros.load()

            return true
        ) catch (
            return false
        )
    )

    -- Create the installer dialog
    rollout eskiInstallerDialog "Eski Layer Manager Installer v0.3.5" width:400 height:300 (

        label lblTitle "Eski Layer Manager - Macro Button Setup" align:#center style_sunkenedge:true offset:[0,10]
        label lblVersion "Installer Version: 0.3.5" align:#center offset:[0,5]

        groupBox grpStatus "Current Status" pos:[10,60] width:380 height:120
        editText lblStatus "" pos:[20,80] width:360 height:90 align:#left readOnly:true

        button btnInstall "Install / Upgrade to Latest Version" pos:[10,190] width:380 height:45
        button btnUninstall "Uninstall Current and Older Versions" pos:[10,245] width:380 height:45

        -- Check status on open
        on eskiInstallerDialog open do (
            if macroExists() then (
                lblStatus.text = "STATUS: Macro button is currently INSTALLED\n\nCategory: Eski Tools\nButton Name: EskiLayerManager"
            ) else (
                lblStatus.text = "STATUS: Macro button is NOT installed\n\nNo macro found in 'Eski Tools' category"
            )
        )

        -- Install/Upgrade button
        on btnInstall pressed do (
            local wasInstalled = macroExists()

            -- First, try to copy the Python script
            local copyResult = copyPythonScript()
            local pythonCopied = copyResult[1]
            local pythonMsg = ""

            if pythonCopied then (
                pythonMsg = "Python script copied from:\n" + copyResult[2] + "\n\n"
            ) else (
                -- Python script not found, but continue with macro installation
                pythonMsg = "WARNING: Could not find eski-layer-manager.py\n" + copyResult[2] + "\n\nYou will need to manually copy it to:\n" + (getDir #scripts) + "\n\n"
            )

            if installMacro() then (
                -- Delay to allow macros to fully reload
                windows.processPostedMessages()

                -- Check if there's a keyboard shortcut assigned
                local hotKeyStr = "No keyboard shortcut assigned"
                local hotKeyFound = false
                -- Note: Hotkey detection is complex and varies by 3ds Max version
                -- Users can check manually in Customize > Customize User Interface > Keyboard tab

                if wasInstalled then (
                    messageBox (pythonMsg + "Macro button UPGRADED successfully!\n\nThe button has been updated to the latest version.\nIf you already have it on a toolbar, it will use the new version automatically.\n\n" + hotKeyStr) title:"Success" beep:false
                ) else (
                    messageBox (pythonMsg + "Macro button INSTALLED successfully!\n\nNext steps:\n1. Press Y or go to: Customize > Customize User Interface\n2. Select category: 'Eski Tools'\n3. Drag 'EskiLayerManager' to any toolbar\n4. Click Save and Close\n\nThen click the button to launch the Layer Manager!\n\n" + hotKeyStr + (if not hotKeyFound then "\n\nTip: You can assign a keyboard shortcut in:\nCustomize > Customize User Interface > Keyboard tab" else "")) title:"Success" beep:false
                )

                -- Print hotkey info to listener as well
                format "Eski Layer Manager installed: %\n" hotKeyStr

                -- Update status
                lblStatus.text = "STATUS: Macro button is currently INSTALLED\n\nCategory: Eski Tools\nButton Name: EskiLayerManager"
            ) else (
                messageBox "Installation FAILED!\n\nCould not create macro file. Check permissions." title:"Error"
            )
        )

        -- Uninstall button
        on btnUninstall pressed do (
            if macroExists() then (
                if queryBox "Are you sure you want to UNINSTALL the Eski Layer Manager?\n\nThis will remove:\n- Macro button file (.mcr)\n- Python script file (.py)\n- Requires 3ds Max restart to fully clear actions\n\n(You can reinstall anytime by running this script again)" title:"Confirm Uninstall" then (
                    if uninstallMacro() then (
                        local msg = "Files REMOVED successfully!\n\n"
                        msg += "✓ Macro button file deleted\n"
                        msg += "✓ Python script deleted\n\n"
                        msg += "NEXT STEPS - Complete Removal:\n\n"
                        msg += "1. Close this dialog\n"
                        msg += "2. Remove button from toolbars (if present)\n"
                        msg += "3. Remove keyboard shortcuts (Customize > Keyboard tab)\n"
                        msg += "4. RESTART 3ds Max\n\n"
                        msg += "After restart, the action will be completely removed from\nthe Customize User Interface lists."

                        messageBox msg title:"Uninstalled - Restart Required" beep:false

                        -- Update status
                        lblStatus.text = "STATUS: Files deleted - RESTART 3ds Max to complete removal\n\nMacro and Python files have been deleted"
                    ) else (
                        messageBox "Uninstallation FAILED!\n\nCould not remove files. Check listener for details." title:"Error"
                    )
                )
            ) else (
                messageBox "No macro button found to uninstall!\n\nThe Eski Layer Manager macro is not currently installed." title:"Nothing to Uninstall" beep:false
            )
        )
    )

    -- Show the dialog
    createDialog eskiInstallerDialog modal:true
)
