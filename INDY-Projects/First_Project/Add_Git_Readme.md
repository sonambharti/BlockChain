                    Git Commands to add your project to Git repository

#01) Create Github Account
#02) Install Git on your PC
#03) Create Git repository from Git Account
#04) Move to directory in your PC and use following command :
     git init
#05) Check status of untracked files 
     git status
#06) Add files to commit
     git add -A
#07) Commit staged files
      git commit -m "message"
#08) Configure username
      git config --global user.username

# Setup SSH for secure transmission (You Can Skip it if already done earlier)

#09) Open git bash 
#10) Check existing SSH Keys
     ls -al ~/.ssh
#11) If don't have ssh key for github then create new
     ssh-keygen -t ed25519 -C "your_email@example.com"
#12) Leave filename and paraphrase blank
#13) Start SSH Agent
     eval "$(ssh-agent -s)"
#14) Add SSH private key to ssh-agent use your private key file name inplace of id_ed25519
     ssh-add ~/.ssh/id_ed25519
#15) Copy public key to clipboard
     clip < ~/.ssh/id_ed25519.pub
#16) Add copied data to github account in ssh keys 
#17) Test if all works perfectly
     ssh -T git@github.com

# SSH setup ends here

#18) Select branch as main
     git branch -M main
#19) Add link between local and git repository
     git remote add origin git@github.com:kartikayt/ktfolio.git
#20) Push committed files to git repo
     git push -u origin main
