# Rebuild for image quality rating
This application should be rebuild for two user tasks:
1) 2-forced choice - Given a group of images, the system should show a pair and user should select the "better" one by clicking on it, touching it, or pressing an left/right arrow key. The pair should be selected from the group in a "clever" way, such that it would balance how informative it is for the task of ordering the group of images and at the same time assesing how well the user himself can order images.
2) Show single image and the user is forced to selecte from low number of options (cicking a button or pressing a hotkey).

The application should support an arbitrary number of tasks. Admin creates the task, specifying name, description, instructions, options for task type 2, uploading images - groups for task of type 1 will be tetermined by a file prefix.

For both types of tasks, the 1) "group" or 2) "image" selection should balance getting more information about the images and assesing reliability of the "user".

The application should preserve leaderboard, points based on user recent reliability. 

Admin should be able also to view ratings, detailed statistics, assign bonusses to tasks ...


Images in a task will have the same size.


After the change, the application should have only this functionality. Any unused code and files should be removed.

The rebuild application should include:
- tests
- documentation

