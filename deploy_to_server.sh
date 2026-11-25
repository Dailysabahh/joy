#!/bin/bash
# Deploy Princess to Joy Server

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     👸  Deploy Princess to Joy Server (13.60.238.119)      ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

SERVER_IP="13.60.238.119"
SERVER_USER="ubuntu"
SSH_KEY="/Users/pro/Downloads/ai_receptionist/AI_Receptionist.pem"
REMOTE_DIR="/home/ubuntu/joy"  # Adjust if different

echo "📦 Creating deployment package..."
echo ""

# Create a temp deployment directory
DEPLOY_DIR="princess_deploy_$(date +%s)"
mkdir -p "$DEPLOY_DIR"

# Copy necessary files
echo "Copying files..."
cp -r config "$DEPLOY_DIR/"
cp -r app "$DEPLOY_DIR/"
cp -r templates "$DEPLOY_DIR/"
cp main.py "$DEPLOY_DIR/"
cp requirements.txt "$DEPLOY_DIR/"

echo "✅ Files packaged"
echo ""

# Create tarball
tar -czf princess_deployment.tar.gz -C "$DEPLOY_DIR" .
rm -rf "$DEPLOY_DIR"

echo "📤 Uploading to server..."
echo ""

# Try to upload
if scp -i "$SSH_KEY" princess_deployment.tar.gz "$SERVER_USER@$SERVER_IP:/tmp/"; then
    echo "✅ Upload successful"
    echo ""
    echo "📦 Deploying on server..."
    
    # SSH and deploy
    ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" << 'EOF'
cd /tmp
tar -xzf princess_deployment.tar.gz -C ~/joy/
cd ~/joy
sudo systemctl restart joy
echo "✅ Princess deployed and Joy restarted!"
EOF

    echo ""
    echo "🎉 DEPLOYMENT COMPLETE!"
    echo ""
    echo "Princess is now available at:"
    echo "  🌐 http://13.60.238.119/princess"
    echo "  🌐 http://13.60.238.119/demo/princess"
    echo ""
    echo "If you have a domain:"
    echo "  🌐 https://your-domain.com/princess"
    echo ""
else
    echo "❌ Upload failed. Please deploy manually:"
    echo ""
    echo "Manual deployment steps:"
    echo "1. Upload princess_deployment.tar.gz to the server"
    echo "2. SSH into the server: ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP"
    echo "3. Extract: cd ~/joy && tar -xzf /tmp/princess_deployment.tar.gz"
    echo "4. Restart Joy: sudo systemctl restart joy"
    echo ""
    echo "The deployment package is ready: princess_deployment.tar.gz"
fi

# Cleanup
rm -f princess_deployment.tar.gz

echo ""
echo "════════════════════════════════════════════════════════════════"
