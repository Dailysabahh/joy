#!/bin/bash
# Quick Princess Deploy Script
# Use this if you have SSH access configured

echo "🚀 Deploying Princess to Joy Server..."
echo ""

# Configuration
SERVER="13.60.238.119"
USER="ubuntu"
REMOTE_PATH="/home/ubuntu/joy"

# Check if we can connect
echo "Testing SSH connection..."
if ssh ${USER}@${SERVER} "echo '✅ SSH Connected'" 2>/dev/null; then
    echo ""
    echo "📤 Uploading Princess files..."
    
    # Upload files
    scp main.py ${USER}@${SERVER}:${REMOTE_PATH}/ && echo "  ✅ main.py"
    scp app/princess_brain.py ${USER}@${SERVER}:${REMOTE_PATH}/app/ && echo "  ✅ princess_brain.py"
    scp config/xtrabrides_knowledge.json ${USER}@${SERVER}:${REMOTE_PATH}/config/ && echo "  ✅ xtrabrides_knowledge.json"
    scp config/princess_persona.json ${USER}@${SERVER}:${REMOTE_PATH}/config/ && echo "  ✅ princess_persona.json"
    scp templates/demo/princess_chat.html ${USER}@${SERVER}:${REMOTE_PATH}/templates/demo/ && echo "  ✅ princess_chat.html"
    
    echo ""
    echo "🔄 Restarting Joy service..."
    ssh ${USER}@${SERVER} "sudo systemctl restart joy || (pkill -f 'python.*main.py' && cd ${REMOTE_PATH} && nohup python3 main.py > /dev/null 2>&1 &)"
    
    echo ""
    echo "🎉 DEPLOYMENT COMPLETE!"
    echo ""
    echo "Princess is now live at:"
    echo "  🌐 http://13.60.238.119/princess"
    echo "  🌐 http://13.60.238.119/demo/princess"
    echo ""
else
    echo "❌ Cannot connect to server"
    echo ""
    echo "Please configure SSH access first:"
    echo "  1. Make sure you can run: ssh ubuntu@13.60.238.119"
    echo "  2. Add your SSH key to the server"
    echo "  3. Or use the manual upload method (see SIMPLE_DEPLOY_GUIDE.md)"
    echo ""
fi
