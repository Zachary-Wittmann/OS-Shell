#! /usr/bin/env python3

import os, sys, re

def find_executable(command):
    # Check if the command is an absolute path
    if os.path.isabs(command) and os.path.exists(command):
        return command

    # Check each directory in the PATH
    for path in os.environ.get("PATH", "").split(os.pathsep):
        executable_path = os.path.join(path, command)
        if os.path.exists(executable_path):
            return executable_path
        
    return None

def execute_command(command, background=False):
    executable_path = find_executable(command)

    if executable_path is None:
        print(f"{command}: command not found", file=sys.stderr)
        return
    
    pid = os.fork()

    if pid == 0:  # Child process
        # Split the command into tokens
        tokens = re.split(r'\s+', command)
        
        # Check for input/output redirection
        if '>' in tokens:
            output_index = tokens.index('>')
            output_file = tokens[output_index + 1]
            tokens = tokens[:output_index]  # Remove '>' and the output file from tokens
            sys.stdout.flush()  # Flush the buffer before redirection
            os.close(1)  # Close standard output
            os.open(output_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)  # Open output file

        if '<' in tokens:
            input_index = tokens.index('<')
            input_file = tokens[input_index + 1]
            tokens = tokens[:input_index]  # Remove '<' and the input file from tokens
            sys.stdin.flush()  # Flush the buffer before redirection
            os.close(0)  # Close standard input
            os.open(input_file, os.O_RDONLY)  # Open input file

        # Check for pipes
        if '|' in tokens:
            pipe_index = tokens.index('|')
            command1 = tokens[:pipe_index]
            command2 = tokens[pipe_index + 1:]
            execute_pipe(command1, command2)
        else:
            try:
                # Execute the command
                os.execve(executable_path, [command] + tokens[1:], os.environ)
            except FileNotFoundError:
                print(f"{command}: command not found", file=sys.stderr)
                sys.exit(1)

    elif pid > 0:  # Parent process
        if not background:
            _, exit_code = os.waitpid(pid, 0)
            if exit_code != 0:
                print(f"Program terminated with exit code {exit_code}", file=sys.stderr)
        else:
            print(f"Background task {pid} started")

def wait_for_background_tasks():
    try:
        while True:
            _, exit_code = os.waitpid(-1, os.WNOHANG)
            if exit_code > 0:
                print(f"Background task terminated with exit code {exit_code}")
            elif exit_code == 0:
                break # No more background tasks
            else:
                break # Error or no more background tasks
    except ChildProcessError:
        pass # No child processes

def execute_pipe(command1, command2):
    # Create a pipe
    pipe_fd = os.pipe()

    pid1 = os.fork()

    if pid1 == 0:  # Child process 1
        os.close(pipe_fd[0])  # Close the read end of the pipe
        os.dup2(pipe_fd[1], 1)  # Redirect standard output to the pipe
        os.close(pipe_fd[1])  # Close the duplicated file descriptor

        try:
            os.execve(command1[0], command1, os.environ)
        except FileNotFoundError:
            print(f"{command1[0]}: command not found", file=sys.stderr)
            sys.exit(1)

    pid2 = os.fork()

    if pid2 == 0:  # Child process 2
        os.close(pipe_fd[1])  # Close the write end of the pipe
        os.dup2(pipe_fd[0], 0)  # Redirect standard input to the pipe
        os.close(pipe_fd[0])  # Close the duplicated file descriptor

        try:
            os.execve(command2[0], command2, os.environ)
        except FileNotFoundError:
            print(f"{command2[0]}: command not found", file=sys.stderr)
            sys.exit(1)

    os.close(pipe_fd[0])  # Close both ends of the pipe in the parent process
    os.close(pipe_fd[1])

    _, _ = os.waitpid(pid1, 0)
    _, exit_code2 = os.waitpid(pid2, 0)

    if exit_code2 != 0:
        print(f"Program terminated with exit code {exit_code2}", file=sys.stderr)

def main():
    # Set the prompt string
    prompt = os.getenv("PS1", "$ ")

    while True:
        # Print the prompt
        sys.stdout.write(prompt)
        sys.stdout.flush()

        # Read the command from the user
        command = input()

        # Check for the "exit" command
        if command == "exit":
            wait_for_background_tasks() # Wait for the background tasks before exiting
            break

        # Check for the "cd" command
        if command.startswith("cd "):
            try:
                os.chdir(command[3:])
            except FileNotFoundError:
                print(f"cd: no such file or directory: {command[3:]}", file=sys.stderr)
        else:
            background = False

            if command.endswith("&"):
                background = True
                command = command[:-1] # Remove the '&'
            
            # Execute the command
            execute_command(command)

            if not background:
                wait_for_background_tasks() # Wait for the background tasks after foreground task

if __name__ == "__main__":
    main()
