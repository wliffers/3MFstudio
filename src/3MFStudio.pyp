<?xml version="1.0" encoding="utf-8"?>
<Element xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="https://pythonparts.allplan.com/2027/schemas/PythonPart.xsd">

    <!-- Auswahl und Einstellungen stehen nur im eigenen Fenster (threemf_window.py); diese Palette zeigt bloss
         eine Info-Zeile, solange das Werkzeug laeuft. -->
    <Script>
        <Name>3MFStudio.py</Name>
        <Title>3MFStudio</Title>
        <Version>1.0</Version>
        <Interactor>False</Interactor>
        <ReadLastInput>False</ReadLastInput>
    </Script>

    <Page>
        <Name>Page1</Name>
        <Text>3MFStudio</Text>
        <Parameters>

            <Parameter>
                <Name>InfoText</Name>
                <Text>Info</Text>
                <Value>Bedienung im 3MFStudio-Fenster</Value>
                <ValueType>String</ValueType>
                <Enable>False</Enable>
                <Persistent>NO</Persistent>
            </Parameter>

        </Parameters>
    </Page>

</Element>
