-- Eski Layer Manager - Macro Button Installer/Uninstaller
-- Run this script to install, upgrade, or uninstall the Layer Manager macro button

(
    -- Version of the installer
    local installerVersion = "0.2.0"

    -- Function to check if macro file exists
    fn macroExists = (
        local macroDir = getDir #userMacros
        local macroFile = macroDir + "\\EskiLayerManager.mcr"
        return doesFileExist macroFile
    )

    -- Function to uninstall existing macros
    fn uninstallMacro = (
        try (
            local macroDir = getDir #userMacros
            local macroFile = macroDir + "\\EskiLayerManager.mcr"

            if doesFileExist macroFile then (
                deleteFile macroFile
                macros.load()
                return true
            ) else (
                return false
            )
        ) catch (
            return false
        )
    )

    -- Function to install/upgrade the macro
    fn installMacro = (
        -- Create the macro script code
        local macroCode = "macroScript EskiLayerManager\n"
        macroCode += "    category:\"Eski Tools\"\n"
        macroCode += "    buttonText:\"Eski\\nLayers\"\n"
        macroCode += "    toolTip:\"Eski Layer Manager by Claude v" + installerVersion + "\"\n"
        macroCode += "    icon:#(\"Schematic\",1)\n"
        macroCode += "(\n"
        macroCode += "    -- This macro button launches the Eski Layer Manager\n"
        macroCode += "    python.Execute \"import sys\"\n"
        macroCode += "    python.Execute \"import importlib\"\n"
        macroCode += "    \n"
        macroCode += "    -- Reload the module in case it was updated\n"
        macroCode += "    python.Execute \"if 'eski_layer_manager' in sys.modules: importlib.reload(sys.modules['eski_layer_manager'])\"\n"
        macroCode += "    \n"
        macroCode += "    -- Import and show the layer manager\n"
        macroCode += "    python.Execute \"import eski_layer_manager\"\n"
        macroCode += "    python.Execute \"eski_layer_manager.show_layer_manager()\"\n"
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
    rollout eskiInstallerDialog "Eski Layer Manager Installer" width:400 height:250 (

        label lblTitle "Eski Layer Manager - Macro Button Setup" align:#center style_sunkenedge:true offset:[0,10]
        label lblVersion "Installer Version: 0.2.0" align:#center offset:[0,5]

        groupBox grpStatus "Current Status" pos:[10,60] width:380 height:80
        editText lblStatus "" pos:[20,80] width:360 height:50 align:#left readOnly:true

        button btnInstall "Install / Upgrade to Latest Version" pos:[10,150] width:380 height:40
        button btnUninstall "Uninstall Current and Older Versions" pos:[10,200] width:380 height:40

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

            if installMacro() then (
                if wasInstalled then (
                    messageBox "Macro button UPGRADED successfully!\n\nThe button has been updated to the latest version.\nIf you already have it on a toolbar, it will use the new version automatically." title:"Success" beep:false
                ) else (
                    messageBox "Macro button INSTALLED successfully!\n\nNext steps:\n1. Press Y or go to: Customize > Customize User Interface\n2. Select category: 'Eski Tools'\n3. Drag 'EskiLayerManager' to any toolbar\n4. Click Save and Close\n\nThen click the button to launch the Layer Manager!" title:"Success" beep:false
                )

                -- Update status
                lblStatus.text = "STATUS: Macro button is currently INSTALLED\n\nCategory: Eski Tools\nButton Name: EskiLayerManager"
            ) else (
                messageBox "Installation FAILED!\n\nCould not create macro file. Check permissions." title:"Error"
            )
        )

        -- Uninstall button
        on btnUninstall pressed do (
            if macroExists() then (
                if queryBox "Are you sure you want to UNINSTALL the Eski Layer Manager macro button?\n\nThis will remove it from the system.\n(You can reinstall anytime by running this script again)" title:"Confirm Uninstall" then (
                    if uninstallMacro() then (
                        messageBox "Macro button UNINSTALLED successfully!\n\nThe button has been removed from the system.\nIf it's still visible on a toolbar, restart 3ds Max to complete removal." title:"Success" beep:false

                        -- Update status
                        lblStatus.text = "STATUS: Macro button is NOT installed\n\nNo macro found in 'Eski Tools' category"
                    ) else (
                        messageBox "Uninstallation FAILED!\n\nCould not remove macro. It may not exist or permissions issue." title:"Error"
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
