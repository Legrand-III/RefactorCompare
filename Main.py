import os
import subprocess

"""

Questions:
1: how do we get version 1 and version 2 during the running
2: how do we import version 1 and version 2 during running
3: how do we expand the tests to work for more inputs (way later ntm)

"""

def main():

    link = input("paste your repo link:\n")
    commit1 = input("input your first commit code:\n")
    commit2 = input("input your second commit code\n")

    compareCommits(link, commit1, commit2)
def compareCommits(link, commit1, commit2):

    #subprocess or bash
    # git clone <repo> Version1
    # git clone <repo> Version2
    # CD version1
    # git checkout <commit1>
    # CD..
    # CD version2
    # git checkout <commit2>

    baseDirectory = os.getcwd()

    """Version1"""

    print("\n===========================\ncloning first commit...")

    #clone!!!
    subprocess.run("git clone " + link + " Version1")
    #save base directory so we can go back
    #CD into version1
    os.chdir("Version1")
    #checkout first commit
    subprocess.run("git checkout " + commit1)

    #go back
    os.chdir(baseDirectory)


    """Version2"""

    print("\n===========================\ncloning second commit")

    subprocess.run("git clone " + link + " Version2")
    #CD into version2
    os.chdir("Version2")
    # checkout second commit
    subprocess.run("git checkout " + commit2)
    # go back
    os.chdir(baseDirectory)


    import Testing

    Testing.beginTests()



if __name__ == "__main__":
    # run the property test
    main()
    print("passed")