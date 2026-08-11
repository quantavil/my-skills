@rem
@rem Copyright 2015 the original author or authors.
@rem
@rem Licensed under the Apache License, Version 2.0 (the "License");
@rem you may not use this file except in compliance with the License.
@rem You may obtain a copy of the License at
@rem
@rem      https://www.apache.org/licenses/LICENSE-2.0
@rem
@rem Unless required by applicable law or agreed to in writing, software
@rem distributed under the License is distributed on an "AS IS" BASIS,
@rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
@rem See the License for the specific language governing permissions and
@rem limitations under the License.
@rem
@rem SPDX-License-Identifier: Apache-2.0
@rem

@if "%DEBUG%"=="" @echo off
@rem ##########################################################################
@rem
@rem  compose-preview startup script for Windows
@rem
@rem ##########################################################################

@rem Set local scope for the variables, and ensure extensions are enabled
setlocal EnableExtensions

set DIRNAME=%~dp0
if "%DIRNAME%"=="" set DIRNAME=.
@rem This is normally unused
set APP_BASE_NAME=%~n0
set APP_HOME=%DIRNAME%..

@rem Resolve any "." and ".." in APP_HOME to make it shorter.
for %%i in ("%APP_HOME%") do set APP_HOME=%%~fi

@rem Add default JVM options here. You can also use JAVA_OPTS and COMPOSE_PREVIEW_OPTS to pass JVM options to this script.
set DEFAULT_JVM_OPTS="--enable-native-access=ALL-UNNAMED"

@rem Find java.exe
if defined JAVA_HOME goto findJavaFromJavaHome

set JAVA_EXE=java.exe
%JAVA_EXE% -version >NUL 2>&1
if %ERRORLEVEL% equ 0 goto execute

echo. 1>&2
echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH. 1>&2
echo. 1>&2
echo Please set the JAVA_HOME variable in your environment to match the 1>&2
echo location of your Java installation. 1>&2

"%COMSPEC%" /c exit 1

:findJavaFromJavaHome
set JAVA_HOME=%JAVA_HOME:"=%
set JAVA_EXE=%JAVA_HOME%/bin/java.exe

if exist "%JAVA_EXE%" goto execute

echo. 1>&2
echo ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME% 1>&2
echo. 1>&2
echo Please set the JAVA_HOME variable in your environment to match the 1>&2
echo location of your Java installation. 1>&2

"%COMSPEC%" /c exit 1

:execute
@rem Setup the command line

set CLASSPATH=%APP_HOME%\lib\compose-preview-0.19.56.jar;%APP_HOME%\lib\gradle-preview-driver-0.19.56.jar;%APP_HOME%\lib\preview-data-api-0.19.56.jar;%APP_HOME%\lib\data-fonts-core-0.19.56.jar;%APP_HOME%\lib\render-session-subprocess-0.19.56.jar;%APP_HOME%\lib\compose-preview-mcp-0.19.56.jar;%APP_HOME%\lib\data-remotecompose-core-0.19.56.jar;%APP_HOME%\lib\render-session-api-0.19.56.jar;%APP_HOME%\lib\core-0.19.56.jar;%APP_HOME%\lib\data-render-core-0.19.56.jar;%APP_HOME%\lib\common-io-0.19.56.jar;%APP_HOME%\lib\data-layoutinspector-core-0.19.56.jar;%APP_HOME%\lib\data-preview-overrides-core-0.19.56.jar;%APP_HOME%\lib\data-theme-core-0.19.56.jar;%APP_HOME%\lib\renderer-xr-client-0.19.56.jar;%APP_HOME%\lib\ktor-client-okhttp-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-client-core-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-server-cio-jvm-3.5.2.jar;%APP_HOME%\lib\kotlin-sdk-server-jvm-0.15.0.jar;%APP_HOME%\lib\kotlin-sdk-core-jvm-0.15.0.jar;%APP_HOME%\lib\ktor-server-websockets-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-server-compression-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-server-sse-jvm-3.5.1.jar;%APP_HOME%\lib\ktor-server-content-negotiation-jvm-3.5.1.jar;%APP_HOME%\lib\ktor-server-core-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-http-cio-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-websocket-serialization-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-serialization-kotlinx-json-jvm-3.5.1.jar;%APP_HOME%\lib\ktor-serialization-kotlinx-jvm-3.5.1.jar;%APP_HOME%\lib\ktor-serialization-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-websockets-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-http-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-events-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-sse-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-network-jvm-3.5.2.jar;%APP_HOME%\lib\ktor-utils-jvm-3.5.2.jar;%APP_HOME%\lib\kotlinx-serialization-json-io-jvm-1.11.0.jar;%APP_HOME%\lib\kotlinx-serialization-core-jvm-1.11.0.jar;%APP_HOME%\lib\kotlinx-serialization-json-jvm-1.11.0.jar;%APP_HOME%\lib\okhttp-jvm-5.4.0.jar;%APP_HOME%\lib\okio-jvm-3.18.1.jar;%APP_HOME%\lib\ktor-io-jvm-3.5.2.jar;%APP_HOME%\lib\kotlinx-coroutines-core-jvm-1.11.0.jar;%APP_HOME%\lib\kotlinx-coroutines-slf4j-1.11.0.jar;%APP_HOME%\lib\kotlin-reflect-2.3.21.jar;%APP_HOME%\lib\kotlin-logging-jvm-8.0.4.jar;%APP_HOME%\lib\kotlinx-io-core-jvm-0.9.1.jar;%APP_HOME%\lib\kotlinx-collections-immutable-jvm-0.5.1.jar;%APP_HOME%\lib\kotlinx-io-bytestring-jvm-0.9.1.jar;%APP_HOME%\lib\kotlin-stdlib-2.4.10.jar;%APP_HOME%\lib\kotlin-build-tools-api-2.4.10.jar;%APP_HOME%\lib\jmdns-3.6.3.jar;%APP_HOME%\lib\classgraph-4.8.186.jar;%APP_HOME%\lib\gradle-tooling-api-9.6.1.jar;%APP_HOME%\lib\slf4j-nop-2.0.17.jar;%APP_HOME%\lib\slf4j-api-2.0.17.jar;%APP_HOME%\lib\annotations-23.0.0.jar;%APP_HOME%\lib\config-1.4.9.jar


@rem Execute compose-preview
@rem endlocal doesn't take effect until after the line is parsed and variables are expanded
@rem which allows us to clear the local environment before executing the java command
endlocal & "%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %COMPOSE_PREVIEW_OPTS%  -classpath "%CLASSPATH%" ee.schimke.composeai.cli.MainKt %* & call :exitWithErrorLevel

:exitWithErrorLevel
@rem Use "%COMSPEC%" /c exit to allow operators to work properly in scripts
"%COMSPEC%" /c exit %ERRORLEVEL%
